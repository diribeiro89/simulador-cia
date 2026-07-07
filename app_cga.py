import streamlit as st
import json
import random
import time
from datetime import datetime, timedelta
import pandas as pd
import database as db

st.set_page_config(
    page_title="Simulador CGA",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="collapsed",
)

ARQUIVO_QUESTOES = "questoes_cga_todos_temas.json"

# -------------------------------------------------------
# Carregar questões
# -------------------------------------------------------
@st.cache_data
def carregar_questoes():
    with open(ARQUIVO_QUESTOES, encoding="utf-8") as f:
        return json.load(f)

questoes = carregar_questoes()
db.init_db()

# -------------------------------------------------------
# Persistência
# -------------------------------------------------------
def persistir_tudo():
    db.save_historico(st.session_state.historico)
    db.save_estado(st.session_state)
    # Leitner e descartes são salvos individualmente
    # (assumindo que o database tem funções específicas)
    if hasattr(st.session_state, 'leitner'):
        for qid, dados in st.session_state.leitner.items():
            db.save_leitner(qid, dados['nivel'], dados['proxima'])
    if hasattr(st.session_state, 'alternativas_descartadas'):
        for qid, letras in st.session_state.alternativas_descartadas.items():
            db.save_descartes(qid, letras)

# -------------------------------------------------------
# Estado com carregamento do banco
# -------------------------------------------------------
def inicializar_estado():
    estado_salvo = db.load_estado()
    
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
        "leitner": {},          # id -> {'nivel': int, 'proxima': str}
        "alternativas_descartadas": {},  # id -> [letras]
    }
    
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    
    for k, v in estado_salvo.items():
        if k in st.session_state:
            st.session_state[k] = v
    
    st.session_state.historico = db.load_historico()
    st.session_state.erros = db.load_erros(questoes)
    
    # Carregar Leitner e descartes do banco
    st.session_state.leitner = db.load_leitner()
    st.session_state.alternativas_descartadas = db.load_descartes()
    
    if st.session_state.questao_atual:
        ids_questoes = {q["id"] for q in questoes}
        if st.session_state.questao_atual.get("id") not in ids_questoes:
            st.session_state.questao_atual = None

inicializar_estado()

# -------------------------------------------------------
# Resets
# -------------------------------------------------------
def resetar_treino():
    st.session_state.questao_atual = None
    st.session_state.respondido = False
    st.session_state.resposta_usuario = None
    persistir_tudo()

def resetar_revisao():
    st.session_state.revisao_lista = []
    st.session_state.revisao_i = 0
    st.session_state.revisao_concluida = False
    st.session_state.respondido = False
    st.session_state.resposta_usuario = None
    persistir_tudo()

def resetar_simulado():
    st.session_state.simulado_questoes = []
    st.session_state.simulado_respostas = {}
    st.session_state.simulado_i = 0
    st.session_state.simulado_ativo = False
    st.session_state.simulado_finalizado = False
    st.session_state.simulado_registrado = False
    st.session_state.inicio_simulado = None
    st.session_state.confirmar_finalizar = False
    persistir_tudo()

# -------------------------------------------------------
# Leitner
# -------------------------------------------------------
INTERVALOS = {1: 1, 2: 3, 3: 7, 4: 15, 5: 30}  # dias

def atualizar_leitner(q_id, acertou):
    """Atualiza nível e próxima revisão para a questão."""
    dados = st.session_state.leitner.get(q_id, {'nivel': 1, 'proxima': None})
    nivel_atual = dados['nivel']
    if acertou:
        novo_nivel = min(nivel_atual + 1, 5)
    else:
        novo_nivel = max(nivel_atual - 1, 1)  # desce um nível ao errar
    dias = INTERVALOS[novo_nivel]
    proxima = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
    st.session_state.leitner[q_id] = {'nivel': novo_nivel, 'proxima': proxima}
    persistir_tudo()

def obter_questoes_para_revisar():
    """Retorna lista de questões (dict) que estão agendadas para revisão."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    ids_revisar = []
    for qid, dados in st.session_state.leitner.items():
        if dados['proxima'] and dados['proxima'] <= hoje:
            ids_revisar.append(qid)
    # Ordena por nível (menor = mais urgente)
    ids_revisar.sort(key=lambda x: st.session_state.leitner[x]['nivel'])
    # Converte para objetos completos
    mapa = {q['id']: q for q in questoes}
    return [mapa[id] for id in ids_revisar if id in mapa]

# -------------------------------------------------------
# Descartar alternativas
# -------------------------------------------------------
def toggle_descarte(q_id, letra):
    """Adiciona ou remove uma alternativa da lista de descartadas."""
    if q_id not in st.session_state.alternativas_descartadas:
        st.session_state.alternativas_descartadas[q_id] = []
    descartadas = st.session_state.alternativas_descartadas[q_id]
    if letra in descartadas:
        descartadas.remove(letra)
    else:
        descartadas.append(letra)
    persistir_tudo()

def render_alternativas_com_descarte(q, key_prefix):
    """
    Exibe as alternativas com botões de descarte ao lado.
    Retorna a letra selecionada (ou None) e as descartadas.
    """
    descartadas = st.session_state.alternativas_descartadas.get(q['id'], [])
    opcoes_validas = [letra for letra in q['opcoes'].keys() if letra not in descartadas]
    
    # Exibe cada alternativa com um botão de descarte
    for letra, texto in q['opcoes'].items():
        col1, col2 = st.columns([0.85, 0.15])
        with col1:
            if letra in descartadas:
                st.markdown(f"~~{letra}) {texto}~~")
            else:
                st.markdown(f"{letra}) {texto}")
        with col2:
            btn_label = "↩️" if letra in descartadas else "✖️"
            if st.button(btn_label, key=f"desc_{q['id']}_{letra}_{key_prefix}"):
                toggle_descarte(q['id'], letra)
                st.rerun()
    
    # Radio com apenas as opções não descartadas
    if opcoes_validas:
        return st.radio(
            "Escolha uma alternativa:",
            opcoes_validas,
            format_func=lambda x: f"{x}) {q['opcoes'][x]}",
            key=f"radio_{q['id']}_{key_prefix}",
        )
    else:
        st.warning("Todas as alternativas foram descartadas! Clique em ↩️ para restaurar.")
        return None

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
        persistir_tudo()

def remover_erro(q):
    st.session_state.erros = [e for e in st.session_state.erros if e["id"] != q["id"]]
    persistir_tudo()

def registrar_resposta(q, resposta, origem="treino"):
    correto = (resposta is not None) and (resposta == q["correta"])
    
    # Atualiza Leitner se for revisão de erros
    if origem == "revisao_erros":
        atualizar_leitner(q['id'], correto)
    
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
    
    persistir_tudo()
    return correto

def filtrar_base(tema="Todos", objetivo="Todos"):
    base = questoes
    if tema != "Todos":
        base = [q for q in base if q.get("tema") == tema]
    if objetivo != "Todos":
        base = [q for q in base if q.get("objetivo") == objetivo]
    return base

# -------------------------------------------------------
# UI Helpers
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
    persistir_tudo()
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
    db.save_historico([])
    db.save_estado(st.session_state)
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
        persistir_tudo()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔀 Nova questão", use_container_width=True):
            st.session_state.questao_atual = escolher_questao(base)
            st.session_state.respondido = False
            st.session_state.resposta_usuario = None
            persistir_tudo()
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

    resposta = render_alternativas_com_descarte(q, f"treino_{q['id']}")

    if not st.session_state.respondido:
        if st.button("✅ Responder", use_container_width=True):
            if resposta is None:
                st.warning("Selecione uma alternativa antes de responder.")
            else:
                st.session_state.resposta_usuario = resposta
                st.session_state.respondido = True
                registrar_resposta(q, resposta, "treino")
                persistir_tudo()
                st.rerun()
    else:
        mostrar_resultado(q, st.session_state.resposta_usuario)
        if st.button("➡️ Próxima questão", use_container_width=True):
            st.session_state.questao_atual = escolher_questao(base)
            st.session_state.respondido = False
            st.session_state.resposta_usuario = None
            persistir_tudo()
            st.rerun()

# =======================================================
# MODO 2 — Revisar erros (com Leitner)
# =======================================================
elif modo == "Revisar erros":
    st.subheader("Revisar erros (Leitner)")

    # Busca questões agendadas para revisão
    questoes_revisar = obter_questoes_para_revisar()
    # Se não houver nenhuma, mostra mensagem
    if not questoes_revisar and st.session_state.erros:
        st.info("Nenhum erro precisa ser revisado hoje. Volte amanhã ou clique em 'Revisar todos'.")
    elif not st.session_state.erros:
        st.info("Você não tem erros salvos. Responda questões para começar.")

    # Opção para forçar revisão de todos os erros (ignorando agenda)
    if st.button("🔁 Revisar todos os erros agora", use_container_width=True):
        # Força a lista com todos os erros (ignora Leitner)
        st.session_state.revisao_lista = st.session_state.erros.copy()
        random.shuffle(st.session_state.revisao_lista)
        st.session_state.revisao_i = 0
        st.session_state.revisao_concluida = False
        st.session_state.respondido = False
        st.session_state.resposta_usuario = None
        persistir_tudo()
        st.rerun()

    if st.session_state.revisao_concluida:
        st.success("🎉 Revisão concluída! Você passou por todos os erros desta sessão.")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔁 Revisar novamente", use_container_width=True):
                resetar_revisao()
                st.rerun()
        with col_b:
            st.metric("Erros ainda salvos", len(st.session_state.erros))
    else:
        # Se não houver lista de revisão, cria a partir das questões agendadas
        if not st.session_state.revisao_lista and questoes_revisar:
            st.session_state.revisao_lista = questoes_revisar
            random.shuffle(st.session_state.revisao_lista)
            st.session_state.revisao_i = 0
            st.session_state.respondido = False
            st.session_state.resposta_usuario = None
            persistir_tudo()

        # Se ainda não tiver lista, para
        if not st.session_state.revisao_lista:
            st.stop()

        total_rev = len(st.session_state.revisao_lista)
        i_rev = st.session_state.revisao_i

        if total_rev == 0:
            st.success("Nenhum erro pendente para revisar.")
            st.stop()

        st.caption(f"Revisando {total_rev} erros agendados.")
        st.progress(
            (i_rev + 1) / total_rev,
            text=f"Erro {i_rev + 1} de {total_rev}",
        )

        q = st.session_state.revisao_lista[i_rev]
        st.divider()
        card_questao(q)

        resposta = render_alternativas_com_descarte(q, f"rev_{q['id']}_{i_rev}")

        if not st.session_state.respondido:
            if st.button("✅ Responder", use_container_width=True):
                if resposta is None:
                    st.warning("Selecione uma alternativa antes de responder.")
                else:
                    st.session_state.resposta_usuario = resposta
                    st.session_state.respondido = True
                    registrar_resposta(q, resposta, "revisao_erros")
                    persistir_tudo()
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
                    persistir_tudo()
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
            persistir_tudo()
            st.rerun()

    if st.session_state.simulado_ativo:
        elapsed = time.time() - st.session_state.inicio_simulado
        restante = max(0.0, st.session_state.duracao_simulado_min * 60 - elapsed)

        if restante <= 0:
            st.warning("⏰ Tempo encerrado. Finalizando automaticamente.")
            st.session_state.simulado_ativo = False
            st.session_state.simulado_finalizado = True
            persistir_tudo()
            st.rerun()

        min_rest = int(restante // 60)
        seg_rest = int(restante % 60)

        sim = st.session_state.simulado_questoes
        i = st.session_state.simulado_i
        q = sim[i]

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

        # No simulado, por simplicidade, usamos o radio sem descarte (ou você pode manter)
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
            persistir_tudo()

        st.divider()
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("◀ Anterior", disabled=(i == 0), use_container_width=True):
                st.session_state.simulado_i -= 1
                st.session_state.confirmar_finalizar = False
                persistir_tudo()
                st.rerun()

        with col2:
            if st.button("Próxima ▶", disabled=(i == len(sim) - 1), use_container_width=True):
                st.session_state.simulado_i += 1
                st.session_state.confirmar_finalizar = False
                persistir_tudo()
                st.rerun()

        with col3:
            nao_resp_n = len(sim) - len(st.session_state.simulado_respostas)
            if not st.session_state.confirmar_finalizar:
                if st.button("🏁 Finalizar", use_container_width=True):
                    if nao_resp_n > 0:
                        st.session_state.confirmar_finalizar = True
                        persistir_tudo()
                        st.rerun()
                    else:
                        st.session_state.simulado_ativo = False
                        st.session_state.simulado_finalizado = True
                        persistir_tudo()
                        st.rerun()
            else:
                if st.button("⚠️ Confirmar mesmo assim", use_container_width=True):
                    st.session_state.simulado_ativo = False
                    st.session_state.simulado_finalizado = True
                    st.session_state.confirmar_finalizar = False
                    persistir_tudo()
                    st.rerun()

        if st.session_state.confirmar_finalizar:
            st.warning(
                f"Você ainda tem **{nao_resp_n}** questão(ões) sem resposta. "
                "Confirme para encerrar ou navegue para respondê-las."
            )

    if st.session_state.simulado_finalizado:
        sim = st.session_state.simulado_questoes
        respostas = st.session_state.simulado_respostas

        if not st.session_state.simulado_registrado:
            for q_item in sim:
                registrar_resposta(q_item, respostas.get(q_item["id"]), "simulado")
            st.session_state.simulado_registrado = True
            persistir_tudo()

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
        )        "respondido": False,
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
    
    # Carrega histórico do banco
    st.session_state.historico = db.load_historico()
    
    # Sobrescreve com valores salvos (se existirem)
    for k, v in defaults.items():
        if k in estado_salvo:
            st.session_state[k] = estado_salvo[k]
        elif k not in st.session_state:
            st.session_state[k] = v
    
    # Reconstroi erros a partir dos IDs salvos
    st.session_state.erros = db.load_erros(questoes)
    
    # Reconstroi acertos
    st.session_state.acertos = estado_salvo.get('acertos_ids', [])
    
    # Verifica se a questão atual existe
    if st.session_state.questao_atual:
        ids_questoes = {q['id'] for q in questoes}
        if st.session_state.questao_atual.get('id') not in ids_questoes:
            st.session_state.questao_atual = None

inicializar_estado()

# -------------------------------------------------------
# Persistência
# -------------------------------------------------------
def persistir_tudo():
    db.save_historico(st.session_state.historico)
    db.save_estado(st.session_state)

# -------------------------------------------------------
# Resets
# -------------------------------------------------------
def resetar_treino():
    st.session_state.questao_atual = None
    st.session_state.respondido = False
    st.session_state.resposta_usuario = None
    persistir_tudo()

def resetar_revisao():
    st.session_state.revisao_lista = []
    st.session_state.revisao_i = 0
    st.session_state.revisao_concluida = False
    st.session_state.respondido = False
    st.session_state.resposta_usuario = None
    persistir_tudo()

def resetar_simulado():
    st.session_state.simulado_questoes = []
    st.session_state.simulado_respostas = {}
    st.session_state.simulado_i = 0
    st.session_state.simulado_ativo = False
    st.session_state.simulado_finalizado = False
    st.session_state.simulado_registrado = False
    st.session_state.inicio_simulado = None
    st.session_state.confirmar_finalizar = False
    persistir_tudo()

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
        persistir_tudo()

def remover_erro(q):
    st.session_state.erros = [e for e in st.session_state.erros if e["id"] != q["id"]]
    persistir_tudo()

def registrar_resposta(q, resposta, origem="treino"):
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
    
    persistir_tudo()
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
    db.save_historico([])
    db.save_estado(st.session_state)
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
        persistir_tudo()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔀 Nova questão", use_container_width=True):
            st.session_state.questao_atual = escolher_questao(base)
            st.session_state.respondido = False
            st.session_state.resposta_usuario = None
            persistir_tudo()
            st.rerun()
    with col2:
        st.metric("Base filtrada", f"{len(base)} questões")

    if st.session_state.questao_atual is None:
        st.session_state.questao_atual = escolher_questao(base)
        persistir_tudo()

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
            persistir_tudo()
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
            persistir_tudo()

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
                    persistir_tudo()
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
            persistir_tudo()
            st.rerun()

    # --- Simulado em andamento ---
    if st.session_state.simulado_ativo:
        elapsed = time.time() - st.session_state.inicio_simulado
        restante = max(0.0, st.session_state.duracao_simulado_min * 60 - elapsed)

        if restante <= 0:
            st.warning("⏰ Tempo encerrado. Finalizando automaticamente.")
            st.session_state.simulado_ativo = False
            st.session_state.simulado_finalizado = True
            persistir_tudo()
            st.rerun()

        min_rest = int(restante // 60)
        seg_rest = int(restante % 60)

        sim = st.session_state.simulado_questoes
        i = st.session_state.simulado_i
        q = sim[i]

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
            persistir_tudo()

        st.divider()
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("◀ Anterior", disabled=(i == 0), use_container_width=True):
                st.session_state.simulado_i -= 1
                st.session_state.confirmar_finalizar = False
                persistir_tudo()
                st.rerun()

        with col2:
            if st.button("Próxima ▶", disabled=(i == len(sim) - 1), use_container_width=True):
                st.session_state.simulado_i += 1
                st.session_state.confirmar_finalizar = False
                persistir_tudo()
                st.rerun()

        with col3:
            nao_resp_n = len(sim) - len(st.session_state.simulado_respostas)
            if not st.session_state.confirmar_finalizar:
                if st.button("🏁 Finalizar", use_container_width=True):
                    if nao_resp_n > 0:
                        st.session_state.confirmar_finalizar = True
                        persistir_tudo()
                        st.rerun()
                    else:
                        st.session_state.simulado_ativo = False
                        st.session_state.simulado_finalizado = True
                        persistir_tudo()
                        st.rerun()
            else:
                if st.button("⚠️ Confirmar mesmo assim", use_container_width=True):
                    st.session_state.simulado_ativo = False
                    st.session_state.simulado_finalizado = True
                    st.session_state.confirmar_finalizar = False
                    persistir_tudo()
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

        if not st.session_state.simulado_registrado:
            for q_item in sim:
                registrar_resposta(q_item, respostas.get(q_item["id"]), "simulado")
            st.session_state.simulado_registrado = True
            persistir_tudo()

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
