import streamlit as st
import json
import random
import time
from datetime import datetime
import pandas as pd

st.set_page_config(
    page_title="Simulador CGA",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="collapsed",
)

ARQUIVO_QUESTOES = "questoes_cga_todos_temas.json"


@st.cache_data
def carregar_questoes():
    with open(ARQUIVO_QUESTOES, encoding="utf-8") as f:
        return json.load(f)


questoes = carregar_questoes()


# -------------------------------------------------------
# Estado
# -------------------------------------------------------
def inicializar_estado():
    defaults = {
        "modo": "Treino livre",
        "filtro_tema_atual": "Todos",
        "filtro_objetivo_atual": "Todos",
        "questao_atual": None,
        "respondido": False,
        "resposta_usuario": None,
        "historico": [],
        "erros": [],
        "acertos": [],
        "simulado_questoes": [],
        "simulado_respostas": {},
        "simulado_i": 0,
        "simulado_ativo": False,
        "simulado_finalizado": False,
        "simulado_registrado": False,
        "inicio_simulado": None,
        "duracao_simulado_min": 180,
        "revisao_lista": [],
        "revisao_i": 0,
        "revisao_concluida": False,
        "confirmar_finalizar": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


inicializar_estado()


# -------------------------------------------------------
# Resets
# -------------------------------------------------------
def resetar_treino():
    st.session_state.questao_atual = None
    st.session_state.respondido = False
    st.session_state.resposta_usuario = None


def resetar_revisao():
    st.session_state.revisao_lista = []
    st.session_state.revisao_i = 0
    st.session_state.revisao_concluida = False
    st.session_state.respondido = False
    st.session_state.resposta_usuario = None


def resetar_simulado():
    st.session_state.simulado_questoes = []
    st.session_state.simulado_respostas = {}
    st.session_state.simulado_i = 0
    st.session_state.simulado_ativo = False
    st.session_state.simulado_finalizado = False
    st.session_state.simulado_registrado = False
    st.session_state.inicio_simulado = None
    st.session_state.confirmar_finalizar = False


# -------------------------------------------------------
# Helpers de questão
# -------------------------------------------------------
def escolher_questao(lista=None):
    base = lista if lista else questoes
    return random.choice(base) if base else None


def adicionar_erro_sem_duplicar(q):
    ids = {e["id"] for e in st.session_state.erros}
    if q["id"] not in ids:
        st.session_state.erros.append(q)


def remover_erro(q):
    st.session_state.erros = [e for e in st.session_state.erros if e["id"] != q["id"]]


def registrar_resposta(q, resposta, origem="treino"):
    """
    Registra resposta no histórico.
    resposta=None → não respondida (simulado): acertou=False.
    """
    correto = (resposta is not None) and (resposta == q["correta"])

    registro = {
        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "id": q["id"],
        "numero_original": q.get("numero_original"),
        "tema": q.get("tema"),
        "codigo": q["codigo"],
        "objetivo": q.get("objetivo"),
        "resposta": resposta,
        "correta": q["correta"],
        "acertou": correto,
        "origem": origem,
    }
    st.session_state.historico.append(registro)

    if correto:
        st.session_state.acertos.append(q["id"])
        if origem == "revisao_erros":
            remover_erro(q)
    else:
        adicionar_erro_sem_duplicar(q)

    return correto


def filtrar_base(tema="Todos", objetivo="Todos"):
    base = questoes
    if tema != "Todos":
        base = [q for q in base if q.get("tema") == tema]
    if objetivo != "Todos":
        base = [q for q in base if q.get("objetivo") == objetivo]
    return base


# -------------------------------------------------------
# Helpers de UI
# -------------------------------------------------------
def card_questao(q, mostrar_objetivo=True):
    num = q.get("numero_original", q["id"])
    st.markdown(f"### Questão {num} — {q['codigo']} | V. {q['versao']}")
    if q.get("tema"):
        st.caption(f"📂 {q['tema']}")
    if mostrar_objetivo and q.get("objetivo"):
        with st.expander("Objetivo da questão"):
            st.write(q["objetivo"])
    st.markdown(q["pergunta"])


def alternativas_radio(q, key, index=None):
    return st.radio(
        "Escolha uma alternativa:",
        list(q["opcoes"].keys()),
        format_func=lambda x: f"{x}) {q['opcoes'][x]}",
        index=index,
        key=key,
    )


def mostrar_resultado(q, resposta):
    if resposta == q["correta"]:
        st.success("✅ Correto!")
    else:
        st.error(
            f"❌ Errado — correta: **{q['correta']}**) "
            f"{q['opcoes'][q['correta']]}"
        )
    with st.expander("Ver explicação", expanded=True):
        st.write(q.get("explicacao", "Sem explicação disponível."))


def estatisticas():
    total = len(st.session_state.historico)
    acertos_n = sum(1 for h in st.session_state.historico if h["acertou"])
    erros_n = total - acertos_n
    taxa = (acertos_n / total * 100) if total else 0.0
    return total, acertos_n, erros_n, taxa


LABEL_ORIGEM = {
    "treino": "Treino livre",
    "revisao_erros": "Revisão de erros",
    "simulado": "Simulado",
}


# -------------------------------------------------------
# Sidebar
# -------------------------------------------------------
st.sidebar.title("📚 Simulador CGA")

modo_options = ["Treino livre", "Revisar erros", "Simulado", "Dashboard"]
modo = st.sidebar.radio(
    "Modo de estudo",
    modo_options,
    index=modo_options.index(st.session_state.modo),
)

if modo != st.session_state.modo:
    st.session_state.modo = modo
    resetar_treino()
    st.rerun()

total_h, acertos_h, erros_h, taxa_h = estatisticas()
st.sidebar.metric("Questões respondidas", total_h)
st.sidebar.metric("Taxa de acerto", f"{taxa_h:.1f}%")
st.sidebar.metric("Erros salvos", len(st.session_state.erros))

st.sidebar.divider()

if st.sidebar.button("🗑️ Zerar histórico", use_container_width=True):
    st.session_state.historico = []
    st.session_state.erros = []
    st.session_state.acertos = []
    resetar_treino()
    resetar_revisao()
    resetar_simulado()
    st.rerun()

# -------------------------------------------------------
# Cabeçalho
# -------------------------------------------------------
st.title("📚 Simulador CGA")
st.caption("Treino, revisão de erros, simulado e dashboard por tema")

temas = sorted({q.get("tema") for q in questoes if q.get("tema")})


# =======================================================
# MODO 1 — Treino livre
# =======================================================
if modo == "Treino livre":
    st.subheader("Treino livre")

    filtro_tema = st.selectbox("Filtrar por tema", ["Todos"] + temas)
    objetivos_disp = sorted({
        q.get("objetivo") for q in questoes
        if q.get("objetivo") and (filtro_tema == "Todos" or q.get("tema") == filtro_tema)
    })
    filtro_objetivo = st.selectbox("Filtrar por objetivo", ["Todos"] + objetivos_disp)
    base = filtrar_base(filtro_tema, filtro_objetivo)

    filtro_mudou = (
        filtro_tema != st.session_state.filtro_tema_atual
        or filtro_objetivo != st.session_state.filtro_objetivo_atual
    )
    questao_fora = (
        st.session_state.questao_atual is not None
        and st.session_state.questao_atual not in base
    )

    if filtro_mudou or questao_fora:
        st.session_state.filtro_tema_atual = filtro_tema
        st.session_state.filtro_objetivo_atual = filtro_objetivo
        st.session_state.questao_atual = escolher_questao(base)
        st.session_state.respondido = False
        st.session_state.resposta_usuario = None

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔀 Nova questão", use_container_width=True):
            st.session_state.questao_atual = escolher_questao(base)
            st.session_state.respondido = False
            st.session_state.resposta_usuario = None
            st.rerun()
    with col2:
        st.metric("Base filtrada", f"{len(base)} questões")

    if st.session_state.questao_atual is None:
        st.session_state.questao_atual = escolher_questao(base)

    q = st.session_state.questao_atual
    if q is None:
        st.warning("Nenhuma questão encontrada para este filtro.")
        st.stop()

    st.divider()
    card_questao(q)

    resposta = alternativas_radio(
        q,
        key=f"treino_{q['id']}_{len(st.session_state.historico)}",
        index=None,
    )

    if not st.session_state.respondido:
        if st.button("✅ Responder", use_container_width=True):
            if resposta is None:
                st.warning("Selecione uma alternativa antes de responder.")
            else:
                st.session_state.resposta_usuario = resposta
                st.session_state.respondido = True
                registrar_resposta(q, resposta, "treino")
                st.rerun()
    else:
        mostrar_resultado(q, st.session_state.resposta_usuario)
        if st.button("➡️ Próxima questão", use_container_width=True):
            st.session_state.questao_atual = escolher_questao(base)
            st.session_state.respondido = False
            st.session_state.resposta_usuario = None
            st.rerun()


# =======================================================
# MODO 2 — Revisar erros
# =======================================================
elif modo == "Revisar erros":
    st.subheader("Revisar erros")

    if not st.session_state.erros:
        st.info(
            "Você ainda não tem erros salvos. "
            "Responda questões no treino ou no simulado para montar sua lista."
        )

    elif st.session_state.revisao_concluida:
        st.success("🎉 Revisão concluída! Você passou por todos os erros desta sessão.")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔁 Revisar novamente", use_container_width=True):
                resetar_revisao()
                st.rerun()
        with col_b:
            st.metric("Erros ainda salvos", len(st.session_state.erros))

    else:
        if not st.session_state.revisao_lista:
            st.session_state.revisao_lista = st.session_state.erros.copy()
            random.shuffle(st.session_state.revisao_lista)
            st.session_state.revisao_i = 0
            st.session_state.respondido = False
            st.session_state.resposta_usuario = None

        total_rev = len(st.session_state.revisao_lista)
        i_rev = st.session_state.revisao_i

        if total_rev == 0:
            st.success("Nenhum erro pendente para revisar.")
            st.stop()

        st.caption(f"Revisando {total_rev} erros desta sessão.")
        st.progress(
            (i_rev + 1) / total_rev,
            text=f"Erro {i_rev + 1} de {total_rev}",
        )

        q = st.session_state.revisao_lista[i_rev]
        st.divider()
        card_questao(q)

        resposta = alternativas_radio(
            q,
            key=f"rev_{q['id']}_{i_rev}_{len(st.session_state.historico)}",
            index=None,
        )

        if not st.session_state.respondido:
            if st.button("✅ Responder", use_container_width=True):
                if resposta is None:
                    st.warning("Selecione uma alternativa antes de responder.")
                else:
                    st.session_state.resposta_usuario = resposta
                    st.session_state.respondido = True
                    registrar_resposta(q, resposta, "revisao_erros")
                    st.rerun()
        else:
            mostrar_resultado(q, st.session_state.resposta_usuario)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("➡️ Próximo erro", use_container_width=True):
                    nxt = i_rev + 1
                    st.session_state.respondido = False
                    st.session_state.resposta_usuario = None
                    if nxt >= total_rev:
                        st.session_state.revisao_lista = []
                        st.session_state.revisao_i = 0
                        st.session_state.revisao_concluida = True
                    else:
                        st.session_state.revisao_i = nxt
                    st.rerun()
            with col2:
                if st.button("🔁 Reiniciar revisão", use_container_width=True):
                    resetar_revisao()
                    st.rerun()


# =======================================================
# MODO 3 — Simulado
# =======================================================
elif modo == "Simulado":
    st.subheader("Simulado")

    # --- Configuração ---
    if not st.session_state.simulado_ativo and not st.session_state.simulado_finalizado:
        filtro_tema_sim = st.selectbox("Tema do simulado", ["Todos"] + temas)
        base_sim = filtrar_base(filtro_tema_sim, "Todos")

        col1, col2 = st.columns(2)
        max_qtd = max(5, len(base_sim))
        qtd = col1.number_input(
            "Quantidade de questões",
            min_value=5,
            max_value=max_qtd,
            value=min(60, max_qtd),
            step=5,
        )
        duracao = col2.number_input(
            "Tempo em minutos",
            min_value=10,
            max_value=240,
            value=180,
            step=10,
        )
        st.info(
            f"📋 **{int(qtd)} questões** &nbsp;|&nbsp; "
            f"⏱️ **{int(duracao)} min** &nbsp;|&nbsp; "
            f"Base disponível: **{len(base_sim)} questões**"
        )

        if st.button("🚀 Iniciar simulado", use_container_width=True):
            qtd_real = int(min(qtd, len(base_sim)))
            st.session_state.simulado_questoes = random.sample(base_sim, qtd_real)
            st.session_state.simulado_respostas = {}
            st.session_state.simulado_i = 0
            st.session_state.simulado_ativo = True
            st.session_state.simulado_finalizado = False
            st.session_state.simulado_registrado = False
            st.session_state.confirmar_finalizar = False
            st.session_state.inicio_simulado = time.time()
            st.session_state.duracao_simulado_min = int(duracao)
            st.rerun()

    # --- Simulado em andamento ---
    if st.session_state.simulado_ativo:
        elapsed = time.time() - st.session_state.inicio_simulado
        restante = max(0.0, st.session_state.duracao_simulado_min * 60 - elapsed)

        if restante <= 0:
            st.warning("⏰ Tempo encerrado. Finalizando automaticamente.")
            st.session_state.simulado_ativo = False
            st.session_state.simulado_finalizado = True
            st.rerun()

        min_rest = int(restante // 60)
        seg_rest = int(restante % 60)

        sim = st.session_state.simulado_questoes
        i = st.session_state.simulado_i
        q = sim[i]

        # Cabeçalho
        col_timer, col_prog = st.columns([1, 3])
        col_timer.metric("⏱️ Tempo restante", f"{min_rest:02d}:{seg_rest:02d}")
        with col_prog:
            respondidas_n = len(st.session_state.simulado_respostas)
            st.progress(
                (i + 1) / len(sim),
                text=f"Questão {i + 1} de {len(sim)} | {respondidas_n} respondidas",
            )

        st.divider()
        card_questao(q, mostrar_objetivo=False)

        opcoes = list(q["opcoes"].keys())
        escolha_atual = st.session_state.simulado_respostas.get(q["id"])
        idx_atual = opcoes.index(escolha_atual) if escolha_atual in opcoes else None

        resposta_sim = st.radio(
            "Escolha:",
            opcoes,
            format_func=lambda x: f"{x}) {q['opcoes'][x]}",
            index=idx_atual,
            key=f"sim_{q['id']}_{i}",
        )

        if resposta_sim is not None:
            st.session_state.simulado_respostas[q["id"]] = resposta_sim

        st.divider()
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("◀ Anterior", disabled=(i == 0), use_container_width=True):
                st.session_state.simulado_i -= 1
                st.session_state.confirmar_finalizar = False
                st.rerun()

        with col2:
            if st.button("Próxima ▶", disabled=(i == len(sim) - 1), use_container_width=True):
                st.session_state.simulado_i += 1
                st.session_state.confirmar_finalizar = False
                st.rerun()

        with col3:
            nao_resp_n = len(sim) - len(st.session_state.simulado_respostas)
            if not st.session_state.confirmar_finalizar:
                if st.button("🏁 Finalizar", use_container_width=True):
                    if nao_resp_n > 0:
                        st.session_state.confirmar_finalizar = True
                        st.rerun()
                    else:
                        st.session_state.simulado_ativo = False
                        st.session_state.simulado_finalizado = True
                        st.rerun()
            else:
                if st.button("⚠️ Confirmar mesmo assim", use_container_width=True):
                    st.session_state.simulado_ativo = False
                    st.session_state.simulado_finalizado = True
                    st.session_state.confirmar_finalizar = False
                    st.rerun()

        if st.session_state.confirmar_finalizar:
            st.warning(
                f"Você ainda tem **{nao_resp_n}** questão(ões) sem resposta. "
                "Confirme para encerrar ou navegue para respondê-las."
            )

    # --- Resultado ---
    if st.session_state.simulado_finalizado:
        sim = st.session_state.simulado_questoes
        respostas = st.session_state.simulado_respostas

        # Registra no histórico uma única vez
        if not st.session_state.simulado_registrado:
            for q_item in sim:
                registrar_resposta(q_item, respostas.get(q_item["id"]), "simulado")
            st.session_state.simulado_registrado = True

        acertos_sim = sum(
            1 for q_item in sim
            if respostas.get(q_item["id"]) == q_item["correta"]
        )
        total_sim = len(sim)
        nao_resp = sum(1 for q_item in sim if respostas.get(q_item["id"]) is None)
        taxa_sim = acertos_sim / total_sim * 100 if total_sim else 0.0

        st.success("✅ Simulado finalizado!")

        c1, c2, c3 = st.columns(3)
        c1.metric("Acertos", f"{acertos_sim}/{total_sim}")
        c2.metric("Taxa de acerto", f"{taxa_sim:.1f}%")
        c3.metric("Não respondidas", nao_resp)
        st.progress(taxa_sim / 100, text=f"Aproveitamento: {taxa_sim:.1f}%")

        # Correção com abas por status
        with st.expander("📋 Ver correção completa", expanded=False):

            def render_correcao(q_item, resp):
                num = q_item.get("numero_original", q_item["id"])
                correto = (resp is not None) and (resp == q_item["correta"])
                nao_respondida = resp is None
                if correto:
                    st.success(f"✅ Q{num} — {q_item['codigo']}: correto ({resp})")
                elif nao_respondida:
                    st.warning(
                        f"⚠️ Q{num} — {q_item['codigo']}: não respondida | "
                        f"correta: **{q_item['correta']}**"
                    )
                else:
                    st.error(
                        f"❌ Q{num} — {q_item['codigo']}: "
                        f"você marcou **{resp}** | correta: **{q_item['correta']}**"
                    )
                with st.expander(f"Explicação — {q_item['codigo']}"):
                    st.write(q_item.get("explicacao", "Sem explicação disponível."))

            tabs = st.tabs(["Todas", "✅ Acertos", "❌ Erros", "⚠️ Não respondidas"])

            with tabs[0]:
                for q_item in sim:
                    render_correcao(q_item, respostas.get(q_item["id"]))

            with tabs[1]:
                lst = [q_item for q_item in sim if respostas.get(q_item["id"]) == q_item["correta"]]
                if lst:
                    for q_item in lst:
                        render_correcao(q_item, respostas.get(q_item["id"]))
                else:
                    st.info("Nenhum acerto.")

            with tabs[2]:
                lst = [
                    q_item for q_item in sim
                    if respostas.get(q_item["id"]) is not None
                    and respostas.get(q_item["id"]) != q_item["correta"]
                ]
                if lst:
                    for q_item in lst:
                        render_correcao(q_item, respostas.get(q_item["id"]))
                else:
                    st.info("Nenhum erro.")

            with tabs[3]:
                lst = [q_item for q_item in sim if respostas.get(q_item["id"]) is None]
                if lst:
                    for q_item in lst:
                        render_correcao(q_item, None)
                else:
                    st.info("Todas as questões foram respondidas.")

        if st.button("🔄 Novo simulado", use_container_width=True):
            resetar_simulado()
            st.rerun()


# =======================================================
# MODO 4 — Dashboard
# =======================================================
elif modo == "Dashboard":
    st.subheader("Dashboard de desempenho")

    total_h, acertos_h, erros_h, taxa_h = estatisticas()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Respondidas", total_h)
    c2.metric("Acertos", acertos_h)
    c3.metric("Erros", erros_h)
    c4.metric("Taxa de acerto", f"{taxa_h:.1f}%")

    if not st.session_state.historico:
        st.info(
            "Ainda não há histórico. "
            "Responda questões no treino, revisão ou simulado para alimentar o painel."
        )
        st.stop()

    df = pd.DataFrame(st.session_state.historico)
    df["acertou_num"] = df["acertou"].astype(int)

    st.divider()

    # --- Por modo de estudo ---
    st.markdown("### Desempenho por modo de estudo")
    por_origem = (
        df.groupby("origem")
        .agg(total=("acertou_num", "count"), acertos=("acertou_num", "sum"))
        .reset_index()
    )
    por_origem["Taxa (%)"] = (por_origem["acertos"] / por_origem["total"] * 100).round(1)
    for _, row in por_origem.iterrows():
        label = LABEL_ORIGEM.get(row["origem"], row["origem"])
        st.progress(
            row["Taxa (%)"] / 100,
            text=f"{label}: {row['Taxa (%)']:.1f}% ({row['acertos']}/{row['total']})",
        )

    st.divider()

    # --- Por tema ---
    st.markdown("### Desempenho por tema")
    tema_df = (
        df.groupby("tema", dropna=False)
        .agg(total=("acertou_num", "count"), acertos=("acertou_num", "sum"))
        .reset_index()
    )
    tema_df["tema"] = tema_df["tema"].fillna("Sem tema")
    tema_df["Taxa (%)"] = (tema_df["acertos"] / tema_df["total"] * 100).round(1)
    tema_df = tema_df.sort_values("Taxa (%)", ascending=False)

    st.bar_chart(tema_df.set_index("tema")["Taxa (%)"])

    with st.expander("📊 Tabela detalhada por tema"):
        st.dataframe(
            tema_df[["tema", "Taxa (%)", "acertos", "total"]].rename(
                columns={"tema": "Tema", "acertos": "Acertos", "total": "Total"}
            ).style.format({"Taxa (%)": "{:.1f}"}),
            use_container_width=True,
        )

    st.divider()

    # --- Por objetivo ---
    st.markdown("### Desempenho por objetivo")
    obj_df = (
        df.groupby("objetivo", dropna=False)
        .agg(total=("acertou_num", "count"), acertos=("acertou_num", "sum"))
        .reset_index()
    )
    obj_df["objetivo"] = obj_df["objetivo"].fillna("Sem objetivo")
    obj_df["Taxa (%)"] = (obj_df["acertos"] / obj_df["total"] * 100).round(1)
    obj_df = obj_df.sort_values("Taxa (%)", ascending=False)
    obj_df["Objetivo curto"] = obj_df["objetivo"].apply(
        lambda x: (x[:57] + "...") if len(x) > 60 else x
    )

    st.bar_chart(obj_df.set_index("Objetivo curto")["Taxa (%)"])

    with st.expander("📊 Tabela detalhada por objetivo"):
        st.dataframe(
            obj_df[["objetivo", "Taxa (%)", "acertos", "total"]].rename(
                columns={"objetivo": "Objetivo", "acertos": "Acertos", "total": "Total"}
            ).style.format({"Taxa (%)": "{:.1f}"}),
            use_container_width=True,
        )

    st.divider()

    # --- Evolução temporal ---
    if len(st.session_state.historico) >= 5:
        st.markdown("### Evolução da taxa de acerto — média móvel (janela 10)")
        df["media_movel"] = (
            df["acertou_num"]
            .rolling(window=10, min_periods=1)
            .mean()
            .mul(100)
            .round(1)
        )
        df.index.name = "Questão #"
        st.line_chart(df["media_movel"])

    st.divider()

    # --- Últimas 10 respostas ---
    st.markdown("### Últimas 10 respostas")
    for h in st.session_state.historico[-10:][::-1]:
        icon = "✅" if h["acertou"] else "❌"
        resp = h["resposta"] if h["resposta"] is not None else "_Não respondida_"
        origem_label = LABEL_ORIGEM.get(h.get("origem"), "—")
        tema_label = h.get("tema") or "—"
        num = h.get("numero_original") or h["id"]
        st.write(
            f"{icon} **{tema_label}** | Q{num} — {h['codigo']} | "
            f"Marcada: **{resp}** | Correta: **{h['correta']}** | "
            f"_{origem_label}_"
        )
