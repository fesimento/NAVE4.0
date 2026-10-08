import calendar
from datetime import datetime
import subprocess
import sys

# Garante a instalação/importação do pacote holidays
try:
    import holidays
except ImportError:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "holidays"]
    )
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
# CONEXÃO COM O GOOGLE SHEETS
# --------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)


def carregar_viagens():
    return conn.read(worksheet="viagens", ttl="0")


def carregar_parametros():
    df_p = conn.read(worksheet="parametros", ttl="0")
    return df_p.iloc[0]


INTEGRANTES = ["Rogério", "Jonatas", "Gustavo", "Felipe", "Edgar"]


def get_datas_fechamento(ano, mes):
    if mes == 1:
        data_inicio = pd.Timestamp(year=ano - 1, month=12, day=15)
    else:
        data_inicio = pd.Timestamp(year=ano, month=mes - 1, day=15)

    data_fim = pd.Timestamp(year=ano, month=mes, day=14)
    return data_inicio, data_fim


# --------------------------------------------------------------------------
# SIDEBAR: MENU PRINCIPAL
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

    # Verificar viagens existentes na data selecionada
    existentes = df_viagens[
        (df_viagens["data"] == data_str) & (df_viagens["status"] != "Rejeitada")
    ]

    if not existentes.empty:
        motoristas_existentes = existentes["motorista"].tolist()
        st.warning(
            f"⚠️ **Atenção:** Já existe viagem registrada para essa data ({data_viagem.strftime('%d/%m/%Y')}) por: **{', '.join(motoristas_existentes)}**!"
        )
        st.info(
            "Se você confirmar o envio, o lançamento irá para a **Aba de Aprovação de Duplicadas**."
        )

    with st.form("form_viagem", clear_on_submit=True):
        motorista = st.selectbox("Motorista (Navegante)", INTEGRANTES)
        submetido = st.form_submit_button("Lançar Viagem")

        if submetido:
            status_inicial = (
                "Pendente (Duplicada)" if not existentes.empty else "Aprovada"
            )
            novo_id = (
                int(df_viagens["id"].max()) + 1 if not df_viagens.empty else 1
            )

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
            conn.update(worksheet="viagens", data=df_atualizado)

            if status_inicial == "Aprovada":
                st.success(
                    f"✅ Viagem de **{motorista}** gravada com sucesso no Google Sheets!"
                )
            else:
                st.warning(
                    f"⚠️ Viagem pendente gravada no Google Sheets! Acesse a aba **Aprovação de Duplicadas**."
                )


# --------------------------------------------------------------------------
# 2. APROVAÇÃO DE VIAGENS DUPLICADAS
# --------------------------------------------------------------------------
elif menu == "⚠️ Aprovação de Duplicadas":
    st.header("⚠️ Aprovação de Viagens Duplicadas")
    st.write(
        "Analise e regularize lançamentos duplicados ou pendentes de confirmação."
    )

    df_viagens = carregar_viagens()

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
                    conn.update(worksheet="viagens", data=df_viagens)
                    st.rerun()

                if btn_excluir:
                    df_viagens = df_viagens[df_viagens["id"] != row["id"]]
                    conn.update(worksheet="viagens", data=df_viagens)
                    st.rerun()
            st.divider()


# --------------------------------------------------------------------------
# 3. CONFIGURAÇÕES E CUSTOS FIXOS
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
        oleo_km = c7.number_input(
            "Óleo troca (KM)", value=float(p["oleo_km"])
        )
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
            conn.update(worksheet="parametros", data=df_param)
            st.success("✅ Parâmetros salvos no Google Sheets!")


# --------------------------------------------------------------------------
# 4. CALENDÁRIO E DASHBOARD DE FECHAMENTO
# --------------------------------------------------------------------------
elif menu == "📅 Calendário e Dashboard":
    p = carregar_parametros()
    df_todas_viagens = carregar_viagens()

    # Filtros de Mês/Ano
    st.subheader("🔍 Filtro do Fechamento Mensal")
    col_mes, col_ano = st.columns(2)
    mes_selecionado = col_mes.selectbox(
        "Mês de Referência do Fechamento",
        range(1, 13),
        index=datetime.now().month - 1,
    )
    ano_selecionado = col_ano.number_input(
        "Ano", value=datetime.now().year, step=1
    )

    data_ini, data_fim = get_datas_fechamento(
        ano_selecionado, mes_selecionado
    )
    st.caption(
        f"📅 **Período de Fechamento:** {data_ini.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}"
    )

    # Filtrar viagens do período
    df_todas_viagens["data_dt"] = pd.to_datetime(df_todas_viagens["data"])
    df_viagens = df_todas_viagens[
        (df_todas_viagens["status"] == "Aprovada")
        & (df_todas_viagens["data_dt"] >= data_ini)
        & (df_todas_viagens["data_dt"] <= data_fim)
    ]

    st.divider()

    # --- CALENDÁRIO MENSAL ---
    st.subheader(
        f"📅 Calendário de Viagens ({mes_selecionado:02d}/{ano_selecionado})"
    )

    feriados_br = holidays.BR(years=ano_selecionado)

    df_mes = df_todas_viagens[
        (df_todas_viagens["status"] == "Aprovada")
        & (df_todas_viagens["data_dt"].dt.month == mes_selecionado)
        & (df_todas_viagens["data_dt"].dt.year == ano_selecionado)
    ]
    motoristas_por_dia = df_mes.set_index("data")["motorista"].to_dict()

    cal = calendar.Calendar(firstweekday=6)
    dias_mes = cal.monthdayscalendar(ano_selecionado, mes_selecionado)
    dias_semana = ["dom.", "seg.", "ter.", "qua.", "qui.", "sex.", "sáb."]

    cal_html = """
    <style>
        .cal-table { width: 100%; border-collapse: collapse; text-align: center; font-family: sans-serif; }
        .cal-table th { padding: 8px; color: #555; font-weight: bold; border-bottom: 2px solid #ddd; }
        .cal-table td { width: 14%; height: 80px; vertical-align: top; border: 1px solid #ccc; padding: 4px; position: relative; }
        .cal-day-num { font-weight: bold; font-size: 14px; text-align: left; }
        .cal-driver { margin-top: 15px; font-weight: 600; font-size: 14px; color: #1E3A8A; }
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
                data_curr = datetime(ano_selecionado, mes_selecionado, dia)
                data_str = data_curr.strftime("%Y-%m-%d")

                is_feriado = data_curr.date() in feriados_br
                nome_feriado = (
                    feriados_br.get(data_curr.date()) if is_feriado else ""
                )
                bg_class = "cal-holiday" if is_feriado else ""

                motorista_dia = motoristas_por_dia.get(data_str, "")

                cal_html += f"<td class='{bg_class}'>"
                cal_html += f"<div class='cal-day-num'>{dia}</div>"
                if is_feriado:
                    cal_html += (
                        f"<span class='holiday-label'>{nome_feriado}</span>"
                    )
                if motorista_dia:
                    cal_html += (
                        f"<div class='cal-driver'>{motorista_dia}</div>"
                    )
                cal_html += "</td>"
        cal_html += "</tr>"
    cal_html += "</table>"

    st.markdown(cal_html, unsafe_allow_html=True)

    st.divider()

    # --- TABELA DE FECHAMENTO FINANCEIRO ---
    st.subheader("📊 Tabela de Fechamento Individual do Período")

    if df_viagens.empty:
        st.info(
            "Nenhuma viagem realizada no período de fechamento selecionado."
        )
    else:
        qtd_integrantes = len(INTEGRANTES)
        total_viagens_grupo = len(df_viagens)

        dirigidas = df_viagens["motorista"].value_counts().to_dict()

        custo_combustivel_dia = (
            p["distancia_dia"] / p["consumo_kml"]
        ) * p["valor_combustivel"]
        custo_pedagio_dia = p["pedagio_dia"]
        custo_oleo_dia = (p["oleo_valor"] / p["oleo_km"]) * p["distancia_dia"]
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
        custo_total_grupo = total_viagens_grupo * custo_total_viagem_unitaria

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