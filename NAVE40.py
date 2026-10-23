import calendar
from datetime import datetime
import subprocess
import sys

# Garante a instalação e importação dos pacotes
for pkg in ["holidays", "crcmod"]:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

import crcmod
import holidays
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# --------------------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Fechamento de Caronas - Nave 40",
    page_icon="🚗",
    layout="wide",
)

# --------------------------------------------------------------------------
# LINK DA SUA PLANILHA NO GOOGLE SHEETS
# --------------------------------------------------------------------------
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1-NQnc7jpcGQ1g0RTu76XXj3h08NhU5QGmxoy_tT3QZk/edit?usp=drive_link/edit"

# CONEXÃO COM O GOOGLE SHEETS
conn = st.connection("gsheets", type=GSheetsConnection)


# --------------------------------------------------------------------------
# GERADOR DE PAYLOAD PIX COPIA E COLA (PADRÃO EMV)
# --------------------------------------------------------------------------
def gerar_payload_pix(chave, nome_recebedor, valor, cidade="SAO PAULO"):
    chave = str(chave).replace(".0", "").strip()
    nome = nome_recebedor[:25].strip()
    cidade = cidade[:15].strip()
    valor_str = f"{valor:.2f}"

    payload = (
        "000201"
        f"26{len(f'0014br.gov.bcb.pix01{len(chave):02d}{chave}'):02d}0014br.gov.bcb.pix01{len(chave):02d}{chave}"
        "52040000"
        "5303986"
        f"54{len(valor_str):02d}{valor_str}"
        "5802BR"
        f"59{len(nome):02d}{nome}"
        f"60{len(cidade):02d}{cidade}"
        "62070503***"
        "6304"
    )

    crc16_func = crcmod.mkCrcFun(
        0x11021, rev=False, initCrc=0xFFFF, xorOut=0x0000
    )
    crc = hex(crc16_func(payload.encode("utf-8"))).upper()[2:].zfill(4)
    return payload + crc


# --------------------------------------------------------------------------
# FUNÇÕES DE LEITURA
# --------------------------------------------------------------------------
def carregar_viagens():
    df = conn.read(spreadsheet=URL_PLANILHA, worksheet="viagens", ttl=0)
    if not df.empty:
        df.columns = df.columns.str.strip().str.lower()
    return df


def carregar_parametros():
    df_p = conn.read(spreadsheet=URL_PLANILHA, worksheet="parametros", ttl=0)
    return df_p.iloc[0]


def carregar_pix():
    try:
        df_pix = conn.read(
            spreadsheet=URL_PLANILHA, worksheet="pix", dtype=str, ttl=0
        )
        if not df_pix.empty:
            df_pix.columns = df_pix.columns.str.strip().str.lower()
            if "chave_pix" in df_pix.columns:
                df_pix["chave_pix"] = (
                    df_pix["chave_pix"]
                    .astype(str)
                    .str.replace(".0", "", regex=False)
                    .str.strip()
                )
        return df_pix
    except Exception:
        return pd.DataFrame(columns=["navegante", "chave_pix"])


def calcular_picles(df_resumo_in, df_pix_in):
    devedores = []
    credores = []

    for _, row in df_resumo_in.iterrows():
        saldo = round(row["Fechamento"], 2)
        if saldo < -0.01:
            devedores.append([row["Navegante"], abs(saldo)])
        elif saldo > 0.01:
            credores.append([row["Navegante"], saldo])

    pix_dict = {}
    if not df_pix_in.empty and "navegante" in df_pix_in.columns:
        pix_dict = df_pix_in.set_index("navegante")["chave_pix"].to_dict()

    transacoes = []
    i, j = 0, 0

    while i < len(devedores) and j < len(credores):
        nome_dev, val_dev = devedores[i]
        nome_cred, val_cred = credores[j]

        pagamento = min(val_dev, val_cred)

        if pagamento > 0.01:
            chave = str(pix_dict.get(nome_cred, "Não cadastrada")).replace(
                ".0", ""
            )
            payload_pix = (
                gerar_payload_pix(chave, nome_cred, pagamento)
                if chave != "Não cadastrada"
                else ""
            )

            transacoes.append(
                {
                    "De (Quem Paga)": nome_dev,
                    "Para (Quem Recebe)": nome_cred,
                    "Valor (R$)": pagamento,
                    "Chave Pix": chave,
                    "Payload Pix": payload_pix,
                }
            )

        devedores[i][1] -= pagamento
        credores[j][1] -= pagamento

        if devedores[i][1] <= 0.01:
            i += 1
        if credores[j][1] <= 0.01:
            j += 1

    return pd.DataFrame(transacoes)


INTEGRANTES = ["Rogerio", "Jonatas", "Gustavo", "Felipe", "Edgar"]


def get_datas_fechamento(ano, mes):
    if mes == 1:
        data_inicio = pd.Timestamp(year=ano - 1, month=12, day=15)
    else:
        data_inicio = pd.Timestamp(year=ano, month=mes - 1, day=15)

    data_fim = pd.Timestamp(year=ano, month=mes, day=14)
    return data_inicio, data_fim


# --------------------------------------------------------------------------
# SIDEBAR
# --------------------------------------------------------------------------
st.sidebar.title("🚗 Nave 40")
menu = st.sidebar.radio(
    "Menu Principais",
    [
        "📅 Calendário e Dashboard",
        "➕ Lançar Viagem",
        "⚠️ Aprovação de Duplicadas",
        "⚙️ Configurações / Custos Fixos",
    ],
)

# --------------------------------------------------------------------------
# 1. LANÇAR VIAGEM
# --------------------------------------------------------------------------
if menu == "➕ Lançar Viagem":
    st.header("📋 Registrar Viagem do Dia")

    data_viagem = st.date_input("Data da viagem", value=datetime.today())
    data_str = data_viagem.strftime("%Y-%m-%d")

    df_viagens = carregar_viagens()

    if not df_viagens.empty and "data" in df_viagens.columns:
        existentes = df_viagens[
            (df_viagens["data"] == data_str)
            & (df_viagens["status"] != "Rejeitada")
        ]
    else:
        existentes = pd.DataFrame()

    if not existentes.empty:
        motoristas_existentes = existentes["motorista"].tolist()
        st.warning(
            f"⚠️ **Atenção:** Já existe viagem registrada para essa data ({data_viagem.strftime('%d/%m/%Y')}) por: **{', '.join(motoristas_existentes)}**!"
        )

    with st.form("form_viagem", clear_on_submit=True):
        motorista = st.selectbox("Motorista (Navegante)", INTEGRANTES)
        submetido = st.form_submit_button("Lançar Viagem")

        if submetido:
            status_inicial = (
                "Pendente (Duplicada)" if not existentes.empty else "Aprovada"
            )
            novo_id = (
                int(df_viagens["id"].max())
                if not df_viagens.empty and "id" in df_viagens.columns
                else 0
            ) + 1

            nova_linha = pd.DataFrame(
                [
                    {
                        "id": novo_id,
                        "data": data_str,
                        "motorista": motorista,
                        "status": status_inicial,
                    }
                ]
            )

            df_atualizado = pd.concat(
                [df_viagens, nova_linha], ignore_index=True
            )
            conn.update(
                spreadsheet=URL_PLANILHA,
                worksheet="viagens",
                data=df_atualizado,
            )

            if status_inicial == "Aprovada":
                st.success(f"✅ Viagem de **{motorista}** gravada com sucesso!")
            else:
                st.warning("⚠️ Viagem pendente gravada!")

# --------------------------------------------------------------------------
# 2. APROVAÇÃO DE DUPLICADAS
# --------------------------------------------------------------------------
elif menu == "⚠️ Aprovação de Duplicadas":
    st.header("⚠️ Aprovação de Viagens Duplicadas")
    df_viagens = carregar_viagens()

    if df_viagens.empty or "data" not in df_viagens.columns:
        st.success("🎉 Nenhuma viagem duplicada encontrada!")
    else:
        duplicadas_datas = df_viagens[
            df_viagens.duplicated(subset=["data"], keep=False)
        ]["data"].unique()
        df_duplicadas = df_viagens[
            (df_viagens["status"] == "Pendente (Duplicada)")
            | (df_viagens["data"].isin(duplicadas_datas))
        ]

        if df_duplicadas.empty:
            st.success("🎉 Nenhuma viagem duplicada encontrada!")
        else:
            for index, row in df_duplicadas.iterrows():
                col1, col2, col3, col4 = st.columns([2, 2, 2, 3])
                col1.write(f"**Data:** {row['data']}")
                col2.write(f"**Motorista:** {row['motorista']}")
                col3.write(f"**Status:** {row['status']}")

                with col4:
                    btn_aprovar = st.button("Aprovar", key=f"ap_{row['id']}")
                    btn_excluir = st.button("Excluir", key=f"del_{row['id']}")

                    if btn_aprovar:
                        df_viagens.loc[
                            df_viagens["id"] == row["id"], "status"
                        ] = "Aprovada"
                        conn.update(
                            spreadsheet=URL_PLANILHA,
                            worksheet="viagens",
                            data=df_viagens,
                        )
                        st.rerun()

                    if btn_excluir:
                        df_viagens = df_viagens[df_viagens["id"] != row["id"]]
                        conn.update(
                            spreadsheet=URL_PLANILHA,
                            worksheet="viagens",
                            data=df_viagens,
                        )
                        st.rerun()
                st.divider()

# --------------------------------------------------------------------------
# 3. CONFIGURAÇÕES
# --------------------------------------------------------------------------
elif menu == "⚙️ Configurações / Custos Fixos":
    st.header("⚙️ Configuração de Parâmetros do Veículo e Custos")
    p = carregar_parametros()

    with st.form("form_custos"):
        st.subheader("Veículo & Consumo")
        c1, c2, c3 = st.columns(3)
        valor_veiculo = c1.number_input(
            "Valor veículo (R$)", value=float(p["valor_veiculo"]), step=1000.0
        )
        distancia_dia = c2.number_input(
            "Distância percorrida (km/dia)",
            value=float(p["distancia_dia"]),
            step=5.0,
        )
        consumo_kml = c3.number_input(
            "Consumo esp. combustível (km/l)",
            value=float(p["consumo_kml"]),
            step=0.5,
        )

        st.subheader("Custos Operacionais Diários")
        c4, c5 = st.columns(2)
        valor_combustivel = c4.number_input(
            "Valor combustível (R$/l)",
            value=float(p["valor_combustivel"]),
            step=0.10,
        )
        pedagio_dia = c5.number_input(
            "Pedágio (R$/dia)", value=float(p["pedagio_dia"]), step=1.0
        )

        st.subheader("Manutenção (Óleo e Pneus)")
        c6, c7, c8, c9 = st.columns(4)
        oleo_valor = c6.number_input(
            "Óleo/filtros (R$)", value=float(p["oleo_valor"])
        )
        oleo_km = c7.number_input("Óleo troca (KM)", value=float(p["oleo_km"]))
        pneus_valor = c8.number_input(
            "Pneus jogo (R$)", value=float(p["pneus_valor"])
        )
        pneus_km = c9.number_input(
            "Pneus troca (KM)", value=float(p["pneus_km"])
        )

        st.subheader("Custos Anuais Fixos")
        c10, c11, c12 = st.columns(3)
        depreciacao_pct = c10.number_input(
            "Depreciação (%)", value=float(p["depreciacao_pct"])
        )
        ipva_pct = c11.number_input(
            "IPVA/Licenciamento (%)", value=float(p["ipva_pct"])
        )
        seguro_ano = c12.number_input(
            "Seguro (R$/ano)", value=float(p["seguro_ano"])
        )

        salvar = st.form_submit_button("💾 Salvar Parâmetros")

        if salvar:
            df_param = pd.DataFrame(
                [
                    {
                        "id": 1,
                        "valor_veiculo": valor_veiculo,
                        "distancia_dia": distancia_dia,
                        "consumo_kml": consumo_kml,
                        "valor_combustivel": valor_combustivel,
                        "pedagio_dia": pedagio_dia,
                        "oleo_valor": oleo_valor,
                        "oleo_km": oleo_km,
                        "pneus_valor": pneus_valor,
                        "pneus_km": pneus_km,
                        "depreciacao_pct": depreciacao_pct,
                        "ipva_pct": ipva_pct,
                        "seguro_ano": seguro_ano,
                    }
                ]
            )
            conn.update(
                spreadsheet=URL_PLANILHA,
                worksheet="parametros",
                data=df_param,
            )
            st.success("✅ Parâmetros salvos!")

# --------------------------------------------------------------------------
# 4. CALENDÁRIO E DASHBOARD
# --------------------------------------------------------------------------
elif menu == "📅 Calendário e Dashboard":
    p = carregar_parametros()
    df_todas_viagens = carregar_viagens()

    MESES_NOME = {
        1: "Janeiro",
        2: "Fevereiro",
        3: "Março",
        4: "Abril",
        5: "Maio",
        6: "Junho",
        7: "Julho",
        8: "Agosto",
        9: "Setembro",
        10: "Outubro",
        11: "Novembro",
        12: "Dezembro",
    }

    st.subheader("🔍 Filtro do Fechamento Mensal")
    col_mes, col_ano = st.columns(2)

    meses_selecionados = col_mes.multiselect(
        "Selecione o(s) Mês(es) de Referência",
        options=list(MESES_NOME.keys()),
        format_func=lambda x: MESES_NOME[x],
        default=[datetime.now().month],
    )

    ano_selecionado = col_ano.number_input(
        "Ano", value=datetime.now().year, step=1
    )

    if not meses_selecionados:
        st.warning("⚠️ Por favor, selecione pelo menos um mês de referência.")
    else:
        intervalos_datas = [
            get_datas_fechamento(ano_selecionado, m) for m in meses_selecionados
        ]

        periodos_str = " | ".join(
            [
                f"{ini.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}"
                for ini, fim in intervalos_datas
            ]
        )
        st.caption(f"📅 **Período(s) de Fechamento:** {periodos_str}")

        if df_todas_viagens.empty or "data" not in df_todas_viagens.columns:
            st.info("Nenhuma viagem cadastrada na planilha.")
            df_viagens = pd.DataFrame()
        else:
            df_todas_viagens["data_dt"] = pd.to_datetime(
                df_todas_viagens["data"], errors="coerce"
            )

            condicao_periodo = pd.Series(False, index=df_todas_viagens.index)
            for ini, fim in intervalos_datas:
                condicao_periodo |= (df_todas_viagens["data_dt"] >= ini) & (
                    df_todas_viagens["data_dt"] <= fim
                )

            df_viagens = df_todas_viagens[
                (df_todas_viagens["status"] == "Aprovada") & condicao_periodo
            ]

        st.divider()

        # TABELA DE FECHAMENTO FINANCEIRO
        st.subheader("📊 Tabela de Fechamento Individual Consolidada")

        if df_viagens.empty:
            st.info("Nenhuma viagem realizada no período selecionado.")
        else:
            qtd_integrantes = len(INTEGRANTES)
            total_viagens_grupo = len(df_viagens)

            dirigidas = df_viagens["motorista"].value_counts().to_dict()

            custo_combustivel_dia = (
                p["distancia_dia"] / p["consumo_kml"]
            ) * p["valor_combustivel"]
            custo_pedagio_dia = p["pedagio_dia"]
            custo_oleo_dia = (
                p["oleo_valor"] / p["oleo_km"]
            ) * p["distancia_dia"]
            custo_pneus_dia = (
                p["pneus_valor"] / p["pneus_km"]
            ) * p["distancia_dia"]

            depr_ano = p["valor_veiculo"] * (p["depreciacao_pct"] / 100.0)
            ipva_ano = p["valor_veiculo"] * (p["ipva_pct"] / 100.0)
            fixos_ano = depr_ano + ipva_ano + p["seguro_ano"]
            custo_fixo_diario = fixos_ano / 365.0

            custo_total_viagem_unitaria = (
                custo_combustivel_dia
                + custo_pedagio_dia
                + custo_oleo_dia
                + custo_pneus_dia
                + custo_fixo_diario
            )
            custo_total_grupo = (
                total_viagens_grupo * custo_total_viagem_unitaria
            )

            rateio_por_pessoa = custo_total_grupo / qtd_integrantes

            resumo = []
            for nave in INTEGRANTES:
                v_dirigida = dirigidas.get(nave, 0)
                km_dirigido = v_dirigida * p["distancia_dia"]

                v_pneus = v_dirigida * custo_pneus_dia
                v_oleo = v_dirigida * custo_oleo_dia
                v_pedagio = v_dirigida * custo_pedagio_dia
                v_prop_fixo = v_dirigida * custo_fixo_diario
                v_comb = v_dirigida * custo_combustivel_dia

                valor_proporcional_gastos = (
                    v_pneus + v_oleo + v_pedagio + v_prop_fixo + v_comb
                )

                fechamento = valor_proporcional_gastos - rateio_por_pessoa

                resumo.append(
                    {
                        "Navegante": nave,
                        "KM": int(km_dirigido),
                        "Viagens Dirigidas": int(v_dirigida),
                        "Pneus": v_pneus,
                        "oleo": v_oleo,
                        "Pedágio": v_pedagio,
                        "Proporcional fixo": v_prop_fixo,
                        "Combustível": v_comb,
                        "Valor proporcional": valor_proporcional_gastos,
                        "Fechamento": fechamento,
                    }
                )

            df_resumo = pd.DataFrame(resumo)

            linha_total = {
                "Navegante": "Total",
                "KM": int(df_resumo["KM"].sum()),
                "Viagens Dirigidas": int(df_resumo["Viagens Dirigidas"].sum()),
                "Pneus": df_resumo["Pneus"].sum(),
                "oleo": df_resumo["oleo"].sum(),
                "Pedágio": df_resumo["Pedágio"].sum(),
                "Proporcional fixo": df_resumo["Proporcional fixo"].sum(),
                "Combustível": df_resumo["Combustível"].sum(),
                "Valor proporcional": df_resumo["Valor proporcional"].sum(),
                "Fechamento": df_resumo["Fechamento"].sum(),
            }

            df_exibicao = pd.concat(
                [df_resumo, pd.DataFrame([linha_total])], ignore_index=True
            )

            st.markdown(
                """
                <style>
                    div[data-testid="stTable"] table th:first-child,
                    div[data-testid="stTable"] table td:first-child {
                        position: sticky;
                        left: 0;
                        background-color: #f9f9f9;
                        z-index: 1;
                        font-weight: bold;
                    }
                </style>
            """,
                unsafe_allow_html=True,
            )

            st.dataframe(
                df_exibicao.style.format(
                    {
                        "Pneus": "R$ {:,.2f}",
                        "oleo": "R$ {:,.2f}",
                        "Pedágio": "R$ {:,.2f}",
                        "Proporcional fixo": "R$ {:,.2f}",
                        "Combustível": "R$ {:,.2f}",
                        "Valor proporcional": "R$ {:,.2f}",
                        "Fechamento": "R$ {:,.2f}",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

            st.divider()

            # TABELA PICLES
            st.subheader("🥒 PICLES — Acerto de Contas (Menor Nº de PIX)")

            df_pix = carregar_pix()
            df_picles = calcular_picles(df_resumo, df_pix)

            if df_picles.empty:
                st.success(
                    "🎉 Todas as contas estão zeradas! Ninguém precisa pagar ninguém."
                )
            else:
                df_picles["Valor Formatado"] = df_picles["Valor (R$)"].apply(
                    lambda x: f"R$ {x:,.2f}"
                )

                # Exibição resumida
                st.dataframe(
                    df_picles[
                        [
                            "De (Quem Paga)",
                            "Para (Quem Recebe)",
                            "Valor Formatado",
                            "Chave Pix",
                        ]
                    ],
                    column_config={
                        "De (Quem Paga)": st.column_config.TextColumn(
                            "De (Quem Paga)"
                        ),
                        "Para (Quem Recebe)": st.column_config.TextColumn(
                            "Para (Quem Recebe)"
                        ),
                        "Valor Formatado": st.column_config.TextColumn("Valor"),
                        "Chave Pix": st.column_config.TextColumn("Chave Pix"),
                    },
                    use_container_width=True,
                    hide_index=True,
                )

                st.write(
                    "📱 **Pix Copia e Cola (Toque no ícone da prancheta à direita da caixa para copiar com o valor exato):**"
                )

                for idx, row in df_picles.iterrows():
                    if (
                        row["Payload Pix"]
                        and row["Payload Pix"] != "Chave não cadastrada"
                    ):
                        st.caption(
                            f"💳 **{row['De (Quem Paga)']}** ➔ **{row['Para (Quem Recebe)']}** ({row['Valor Formatado']}):"
                        )
                        st.code(row["Payload Pix"], language="text")
                    else:
                        st.warning(
                            f"⚠️ Chave Pix de **{row['Para (Quem Recebe)']}** não cadastrada na aba 'pix'."
                        )

        st.divider()

        # CALENDÁRIO MENSAL
        st.subheader("📅 Calendário de Viagens")

        feriados_br = holidays.BR(years=ano_selecionado)

        df_aprovadas_todas = (
            df_todas_viagens[df_todas_viagens["status"] == "Aprovada"]
            if not df_todas_viagens.empty
            else pd.DataFrame()
        )

        motoristas_por_dia = (
            df_aprovadas_todas.set_index("data")["motorista"].to_dict()
            if not df_aprovadas_todas.empty
            else {}
        )

        cal = calendar.Calendar(firstweekday=6)
        dias_semana = ["dom.", "seg.", "ter.", "qua.", "qui.", "sex.", "sáb."]

        for m_sel in sorted(meses_selecionados):
            st.markdown(f"#### 🗓️ {MESES_NOME[m_sel]} / {ano_selecionado}")
            dias_mes = cal.monthdayscalendar(ano_selecionado, m_sel)

            cal_html = """
            <style>
                .cal-table { width: 100%; border-collapse: collapse; text-align: center; font-family: sans-serif; margin-bottom: 20px; }
                .cal-table th { padding: 8px; color: #555; font-weight: bold; border-bottom: 2px solid #ddd; }
                .cal-table td { width: 14%; height: 75px; vertical-align: top; border: 1px solid #ccc; padding: 4px; position: relative; }
                .cal-day-num { font-weight: bold; font-size: 13px; text-align: left; }
                .cal-driver { margin-top: 10px; font-weight: 600; font-size: 13px; color: #1E3A8A; }
                .cal-holiday { background-color: #FEE2E2; }
                .holiday-label { font-size: 9px; color: #DC2626; display: block; margin-top: 2px; }
            </style>
            <table class="cal-table">
                <tr>
            """
            for d in dias_semana:
                cor = "color: red;" if d in ["dom.", "sáb."] else ""
                cal_html += f"<th style='{cor}'>{d}</th>"
            cal_html += "</tr>"

            for semana in dias_mes:
                cal_html += "<tr>"
                for dia in semana:
                    if dia == 0:
                        cal_html += "<td></td>"
                    else:
                        data_curr = datetime(ano_selecionado, m_sel, dia)
                        data_str = data_curr.strftime("%Y-%m-%d")

                        is_feriado = data_curr.date() in feriados_br
                        nome_feriado = (
                            feriados_br.get(data_curr.date())
                            if is_feriado
                            else ""
                        )
                        bg_class = "cal-holiday" if is_feriado else ""

                        motorista_dia = motoristas_por_dia.get(data_str, "")

                        cal_html += f"<td class='{bg_class}'>"
                        cal_html += f"<div class='cal-day-num'>{dia}</div>"
                        if is_feriado:
                            cal_html += f"<span class='holiday-label'>{nome_feriado}</span>"
                        if motorista_dia:
                            cal_html += f"<div class='cal-driver'>{motorista_dia}</div>"
                        cal_html += "</td>"
                cal_html += "</tr>"
            cal_html += "</table>"

            st.markdown(cal_html, unsafe_allow_html=True)