# --------------------------------------------------------------------------
# 4. CALENDÁRIO E DASHBOARD DE FECHAMENTO
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

    # Filtros de Mês/Ano
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
        st.warning(
            "⚠️ Por favor, selecione pelo menos um mês de referência no filtro acima."
        )
    else:
        intervalos_datas = [
            get_datas_fechamento(ano_selecionado, m)
            for m in meses_selecionados
        ]

        periodos_str = " | ".join(
            [
                f"{ini.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}"
                for ini, fim in intervalos_datas
            ]
        )
        st.caption(f"📅 **Período(s) de Fechamento:** {periodos_str}")

        if df_todas_viagens.empty or "data" not in df_todas_viagens.columns:
            st.info(
                "Nenhuma viagem cadastrada na planilha ou a coluna 'data' não foi encontrada."
            )
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

        # --- TABELA DE FECHAMENTO FINANCEIRO CONSOLIDADA ---
        st.subheader("📊 Tabela de Fechamento Individual Consolidada")

        if df_viagens.empty:
            st.info(
                "Nenhuma viagem realizada no(s) período(s) de fechamento selecionado(s)."
            )
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

            # --------------------------------------------------------------------------
            # TABELA PICLES - RESUMO DE QUEM PAGA PARA QUEM (Otimizado)
            # --------------------------------------------------------------------------
            st.subheader("🥒 PICLES — Acerto de Contas (Menor Nº de PIX)")

            # Função de cálculo
            def calcular_picles(df_resumo_in):
                devedores = []
                credores = []

                for _, row in df_resumo_in.iterrows():
                    saldo = round(row["Fechamento"], 2)
                    if saldo < -0.01:
                        devedores.append([row["Navegante"], abs(saldo)])
                    elif saldo > 0.01:
                        credores.append([row["Navegante"], saldo])

                transacoes = []
                i, j = 0, 0

                while i < len(devedores) and j < len(credores):
                    nome_dev, val_dev = devedores[i]
                    nome_cred, val_cred = credores[j]

                    pagamento = min(val_dev, val_cred)

                    if pagamento > 0.01:
                        transacoes.append(
                            {
                                "De (Quem Paga)": nome_dev,
                                "Para (Quem Recebe)": nome_cred,
                                "Valor (R$)": pagamento,
                            }
                        )

                    devedores[i][1] -= pagamento
                    credores[j][1] -= pagamento

                    if devedores[i][1] <= 0.01:
                        i += 1
                    if credores[j][1] <= 0.01:
                        j += 1

                return pd.DataFrame(transacoes)

            df_picles = calcular_picles(df_resumo)

            if df_picles.empty:
                st.success(
                    "🎉 Todas as contas estão zeradas! Ninguém precisa pagar ninguém."
                )
            else:
                col_p1, col_p2 = st.columns([2, 1])

                with col_p1:
                    st.dataframe(
                        df_picles.style.format({"Valor (R$)": "R$ {:,.2f}"}),
                        use_container_width=True,
                        hide_index=True,
                    )

                with col_p2:
                    st.info(
                        "💡 **Regra PICLES:** Esta tabela calcula a combinação ideal para quitar todas as dívidas do período com o menor número possível de transferências."
                    )

        st.divider()

        # --- CALENDÁRIO MENSAL ---
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