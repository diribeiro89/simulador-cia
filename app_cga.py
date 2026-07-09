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
# Configuração da Prova (ANBIMA CGA) – 45 questões
# -------------------------------------------------------
GRUPOS_PROVA = [
    {
        "nome": "Gestão de Carteiras – Renda Variável",
        "temas_json": ["CGA - Gestão de Carteiras Renda Variável"],
        "proporcao": 20
    },
    {
        "nome": "Gestão de Carteiras – Renda Fixa",
        "temas_json": ["CGA - Gestão de Carteiras - Renda Fixa"],
        "proporcao": 20
    },
    {
        "nome": "Investimentos no Exterior",
        "temas_json": ["CGA - Investimentos no Exterior"],
        "proporcao": 13
    },
    {
        "nome": "Avaliação de Desempenho",
        "temas_json": ["CGA - Avaliação de Desempenho"],
        "proporcao": 13
    },
    {
        "nome": "Gestão de Risco",
        "temas_json": ["CGA - Gestão de Investimentos e de Risco"],
        "proporcao": 13
    },
    {
        "nome": "Legislação, Regulação e Tributação",
        "temas_json": [
            "CGA - Legislação, Regulação e Melhores Práticas",
            "CGA - Tributação de Fundos de Investimento"
        ],
        "proporcao": 21,
        "subproporcoes": [11, 10]
    }
]

TOTAL_QUESTOES_PROVA = 45
TEMPO_PROVA_MIN = 150

def distribuir_questoes(total, grupos):
    distribuicao = []
    for grupo in grupos:
        qtd_grupo = int(round(total * grupo["proporcao"] / 100))
        if "subproporcoes" in grupo:
            sub_total = sum(grupo["subproporcoes"])
            for tema, sub_prop in zip(grupo["temas_json"], grupo["subproporcoes"]):
                qtd_tema = int(round(qtd_grupo * sub_prop / sub_total))
                distribuicao.append({
                    "grupo_nome": grupo["nome"],
                    "tema_json": tema,
                    "quantidade": qtd_tema
                })
            diff = qtd_grupo - sum(item["quantidade"] for item in distribuicao if item["grupo_nome"] == grupo["nome"])
            if diff != 0:
                for item in distribuicao:
                    if item["grupo_nome"] == grupo["nome"]:
                        item["quantidade"] += diff
                        break
        else:
            distribuicao.append({
                "grupo_nome": grupo["nome"],
                "tema_json": grupo["temas_json"][0],
                "quantidade": qtd_grupo
            })
    total_distribuido = sum(item["quantidade"] for item in distribuicao)
    diff = total - total_distribuido
    if diff != 0 and distribuicao:
        distribuicao[0]["quantidade"] += diff
    return distribuicao

# -------------------------------------------------------
# Persistência
# -------------------------------------------------------
def persistir_tudo():
    db.save_historico(st.session_state.historico)
    db.save_estado(st.session_state)
    if hasattr(st.session_state, 'leitner'):
        for qid, dados in st.session_state.leitner.items():
            db.save_leitner(qid, dados['nivel'], dados['proxima'])
    if hasattr(st.session_state, 'alternativas_descartadas'):
        for qid, letras in st.session_state.alternativas_descartadas.items():
            db.save_descartes(qid, letras)

# -------------------------------------------------------
# Estado
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
        "leitner": {},
        "alternativas_descartadas": {},
        "prova_questoes": [],
        "prova_respostas": {},
        "prova_grupo_por_questao": {},
        "prova_i": 0,
        "prova_ativo": False,
        "prova_finalizado": False,
        "prova_registrado": False,
        "inicio_prova": None,
        "prova_duracao_min": TEMPO_PROVA_MIN,
        "prova_tempo_restante": None,
        "destacadas": db.carregar_destacadas(),  # carrega do banco
        "confirmar_zerar": False,
        # Novos campos para revisão interativa de destacadas
        "destacada_lista": [],
        "destacada_i": 0,
        "destacada_respondido": False,
        "destacada_resposta": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    for k, v in estado_salvo.items():
        if k in st.session_state:
            st.session_state[k] = v
    st.session_state.historico = db.load_historico()
    st.session_state.erros = db.load_erros(questoes)
    st.session_state.leitner = db.load_leitner()
    st.session_state.alternativas_descartadas = db.load_descartes()
    # recarregar destacadas para garantir
    st.session_state.destacadas = db.carregar_destacadas()
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

def resetar_prova():
    st.session_state.prova_questoes = []
    st.session_state.prova_respostas = {}
    st.session_state.prova_grupo_por_questao = {}
    st.session_state.prova_i = 0
    st.session_state.prova_ativo = False
    st.session_state.prova_finalizado = False
    st.session_state.prova_registrado = False
    st.session_state.inicio_prova = None
    st.session_state.confirmar_finalizar = False
    persistir_tudo()

def resetar_destacada():
    st.session_state.destacada_lista = []
    st.session_state.destacada_i = 0
    st.session_state.destacada_respondido = False
    st.session_state.destacada_resposta = None

# -------------------------------------------------------
# Leitner
# -------------------------------------------------------
INTERVALOS = {1: 1, 2: 3, 3: 7, 4: 15, 5: 30}

def atualizar_leitner(q_id, acertou):
    dados = st.session_state.leitner.get(q_id, {'nivel': 1, 'proxima': None})
    nivel_atual = dados['nivel']
    if acertou:
        novo_nivel = min(nivel_atual + 1, 5)
    else:
        novo_nivel = max(nivel_atual - 1, 1)
    dias = INTERVALOS[novo_nivel]
    proxima = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
    st.session_state.leitner[q_id] = {'nivel': novo_nivel, 'proxima': proxima}
    persistir_tudo()

def obter_questoes_para_revisar():
    hoje = datetime.now().strftime("%Y-%m-%d")
    ids_revisar = []
    for qid, dados in st.session_state.leitner.items():
        if dados['proxima'] and dados['proxima'] <= hoje:
            ids_revisar.append(qid)
    ids_revisar.sort(key=lambda x: st.session_state.leitner[x]['nivel'])
    mapa = {q['id']: q for q in questoes}
    return [mapa[id] for id in ids_revisar if id in mapa]

# -------------------------------------------------------
# Descartar alternativas (COM DESTAQUE VISUAL)
# -------------------------------------------------------
def toggle_descarte(q_id, letra):
    if q_id not in st.session_state.alternativas_descartadas:
        st.session_state.alternativas_descartadas[q_id] = []
    descartadas = st.session_state.alternativas_descartadas[q_id]
    if letra in descartadas:
        descartadas.remove(letra)
    else:
        descartadas.append(letra)
    persistir_tudo()

def render_alternativas_com_descarte(q, key_prefix):
    descartadas = st.session_state.alternativas_descartadas.get(q['id'], [])
    opcoes = list(q['opcoes'].keys())
    resposta_key = f"resposta_{q['id']}_{key_prefix}"
    if resposta_key not in st.session_state:
        st.session_state[resposta_key] = None
    
    if st.session_state[resposta_key] in descartadas:
        st.session_state[resposta_key] = None
    
    st.markdown("**Alternativas:**")
    for letra in opcoes:
        is_descartada = letra in descartadas
        is_selecionada = (st.session_state[resposta_key] == letra)
        
        col1, col2 = st.columns([0.85, 0.15])
        with col1:
            label = f"{letra}) {q['opcoes'][letra]}"
            if is_descartada:
                st.markdown(f"~~{label}~~")
            else:
                if is_selecionada:
                    st.markdown(f"""
                        <div style="
                            background-color: #0d3b0d; 
                            color: #9aff9a; 
                            padding: 8px 12px; 
                            border-radius: 8px; 
                            border: 1px solid #2a7a2a; 
                            font-weight: bold;
                            cursor: default;
                        ">
                        {label}
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    if st.button(label, key=f"sel_{q['id']}_{letra}_{key_prefix}", use_container_width=True):
                        st.session_state[resposta_key] = letra
                        st.rerun()
        with col2:
            btn_label = "↩️" if is_descartada else "✖️"
            if st.button(btn_label, key=f"desc_{q['id']}_{letra}_{key_prefix}"):
                toggle_descarte(q['id'], letra)
                if st.session_state[resposta_key] == letra:
                    st.session_state[resposta_key] = None
                st.rerun()
    
    return st.session_state[resposta_key]

# -------------------------------------------------------
# Destaques (salvar no banco)
# -------------------------------------------------------
def toggle_destaque(q_id):
    if q_id in st.session_state.destacadas:
        st.session_state.destacadas.remove(q_id)
        db.remover_destacada(q_id)
    else:
        st.session_state.destacadas.add(q_id)
        db.adicionar_destacada(q_id)

# -------------------------------------------------------
# UI Helpers (card da questão com botão de destaque)
# -------------------------------------------------------
def card_questao(q, mostrar_objetivo=True, mostrar_destaque=False):
    num = q.get("numero_original", q["id"])
    cols = st.columns([1, 0.1]) if mostrar_destaque else st.columns([1])
    with cols[0]:
        st.markdown(f"### Questão {num} — {q['codigo']} | V. {q['versao']}")
    if mostrar_destaque:
        with cols[1]:
            is_dest = q['id'] in st.session_state.destacadas
            if st.button("⭐" if is_dest else "☆", key=f"dest_{q['id']}"):
                toggle_destaque(q['id'])
                st.rerun()
    if q.get("tema"):
        st.caption(f"📂 {q['tema']}")
    if mostrar_objetivo and q.get("objetivo"):
        with st.expander("Objetivo da questão"):
            st.write(q["objetivo"])
    st.markdown(q["pergunta"])

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
    "prova": "Prova ANBIMA",
}

# -------------------------------------------------------
# Sidebar (com confirmação de senha)
# -------------------------------------------------------
st.sidebar.title("📚 Simulador CGA")

modo_options = ["Treino livre", "Revisar erros", "Simulado", "Prova", "Histórico de Provas", "Questões Destacadas", "Dashboard"]
modo = st.sidebar.radio(
    "Modo de estudo",
    modo_options,
    index=modo_options.index(st.session_state.modo),
)

if modo != st.session_state.modo:
    st.session_state.modo = modo
    if modo != "Questões Destacadas":
        resetar_destacada()
    resetar_treino()
    persistir_tudo()
    st.rerun()

total_h, acertos_h, erros_h, taxa_h = estatisticas()
st.sidebar.metric("Questões respondidas", total_h)
st.sidebar.metric("Taxa de acerto", f"{taxa_h:.1f}%")
st.sidebar.metric("Erros salvos", len(st.session_state.erros))
st.sidebar.metric("⭐ Destacadas", len(st.session_state.destacadas))

st.sidebar.divider()

# Botão zerar com confirmação de senha
if st.sidebar.button("🗑️ Zerar histórico", use_container_width=True):
    st.session_state.confirmar_zerar = True

if st.session_state.confirmar_zerar:
    with st.sidebar.expander("🔒 Confirmar exclusão", expanded=True):
        st.warning("Esta ação apagará todo o histórico, erros, acertos, provas e destacadas. Digite a senha para confirmar.")
        senha = st.text_input("Senha:", type="password", key="senha_zerar")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirmar", use_container_width=True):
                if senha == "Bela2307":
                    st.session_state.historico = []
                    st.session_state.erros = []
                    st.session_state.acertos = []
                    st.session_state.destacadas = set()
                    resetar_treino()
                    resetar_revisao()
                    resetar_simulado()
                    resetar_prova()
                    resetar_destacada()
                    db.save_historico([])
                    db.save_estado(st.session_state)
                    db.limpar_provas()
                    db.limpar_destacadas()
                    st.session_state.confirmar_zerar = False
                    st.success("✅ Histórico zerado com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Senha incorreta. Tente novamente.")
        with col2:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state.confirmar_zerar = False
                st.rerun()

# -------------------------------------------------------
# Cabeçalho
# -------------------------------------------------------
st.title("📚 Simulador CGA")
st.caption("Treino, revisão de erros, simulado, prova ANBIMA e dashboard")

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
    card_questao(q, mostrar_destaque=True)

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

    questoes_revisar = obter_questoes_para_revisar()
    if not questoes_revisar and st.session_state.erros:
        st.info("Nenhum erro precisa ser revisado hoje. Volte amanhã ou clique em 'Revisar todos'.")
    elif not st.session_state.erros:
        st.info("Você não tem erros salvos. Responda questões para começar.")

    if st.button("🔁 Revisar todos os erros agora", use_container_width=True):
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
        if not st.session_state.revisao_lista and questoes_revisar:
            st.session_state.revisao_lista = questoes_revisar
            random.shuffle(st.session_state.revisao_lista)
            st.session_state.revisao_i = 0
            st.session_state.respondido = False
            st.session_state.resposta_usuario = None
            persistir_tudo()

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
        card_questao(q, mostrar_destaque=True)

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
# MODO 3 — Simulado (personalizado)
# =======================================================
elif modo == "Simulado":
    st.subheader("Simulado personalizado")

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
        card_questao(q, mostrar_objetivo=False, mostrar_destaque=True)

        resposta_sim = render_alternativas_com_descarte(q, f"sim_{q['id']}_{i}")

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
# MODO 4 — Prova ANBIMA (com mapa de questões)
# =======================================================
elif modo == "Prova":
    st.subheader("📝 Prova ANBIMA CGA")
    st.caption(f"{TOTAL_QUESTOES_PROVA} questões | 2h30 | Proporções oficiais")

    if not st.session_state.prova_ativo and not st.session_state.prova_finalizado:
        distribuicao = distribuir_questoes(TOTAL_QUESTOES_PROVA, GRUPOS_PROVA)
        
        st.info("**Distribuição das questões:**")
        grupos_dict = {}
        for item in distribuicao:
            grupo = item["grupo_nome"]
            if grupo not in grupos_dict:
                grupos_dict[grupo] = []
            grupos_dict[grupo].append((item["tema_json"], item["quantidade"]))
        
        for grupo, temas in grupos_dict.items():
            if len(temas) == 1:
                tema, qtd = temas[0]
                st.write(f"- {grupo}: {qtd} questões ({tema})")
            else:
                st.write(f"- {grupo}:")
                for tema, qtd in temas:
                    st.write(f"    - {tema}: {qtd} questões")
        
        faltam = False
        for item in distribuicao:
            tema_json = item["tema_json"]
            qtd_necessaria = item["quantidade"]
            disponiveis = len([q for q in questoes if q.get("tema") == tema_json])
            if disponiveis < qtd_necessaria:
                faltam = True
                st.error(f"❌ Tema '{tema_json}' tem apenas {disponiveis} questões, mas são necessárias {qtd_necessaria}.")
        if faltam:
            st.warning("Não há questões suficientes para montar a prova. Adicione mais questões ao banco.")
            st.stop()
        
        if st.button("🚀 Iniciar Prova", use_container_width=True):
            questoes_prova = []
            grupo_por_questao = {}
            for item in distribuicao:
                tema_json = item["tema_json"]
                qtd = item["quantidade"]
                grupo_nome = item["grupo_nome"]
                qs_tema = [q for q in questoes if q.get("tema") == tema_json]
                amostra = random.sample(qs_tema, qtd)
                for q in amostra:
                    grupo_por_questao[q["id"]] = grupo_nome
                questoes_prova.extend(amostra)
            random.shuffle(questoes_prova)
            
            st.session_state.prova_questoes = questoes_prova
            st.session_state.prova_respostas = {}
            st.session_state.prova_grupo_por_questao = grupo_por_questao
            st.session_state.prova_i = 0
            st.session_state.prova_ativo = True
            st.session_state.prova_finalizado = False
            st.session_state.prova_registrado = False
            st.session_state.confirmar_finalizar = False
            st.session_state.inicio_prova = time.time()
            st.session_state.prova_duracao_min = TEMPO_PROVA_MIN
            persistir_tudo()
            st.rerun()

    if st.session_state.prova_ativo:
        elapsed = time.time() - st.session_state.inicio_prova
        restante = max(0.0, st.session_state.prova_duracao_min * 60 - elapsed)

        if restante <= 0:
            st.warning("⏰ Tempo encerrado. Finalizando automaticamente.")
            st.session_state.prova_ativo = False
            st.session_state.prova_finalizado = True
            persistir_tudo()
            st.rerun()

        min_rest = int(restante // 60)
        seg_rest = int(restante % 60)

        prov = st.session_state.prova_questoes
        i = st.session_state.prova_i
        q = prov[i]

        col_timer, col_prog = st.columns([1, 3])
        col_timer.metric("⏱️ Tempo restante", f"{min_rest:02d}:{seg_rest:02d}")
        with col_prog:
            respondidas_n = len(st.session_state.prova_respostas)
            st.progress(
                (i + 1) / len(prov),
                text=f"Questão {i + 1} de {len(prov)} | {respondidas_n} respondidas",
            )

        # --- MAPA DE QUESTÕES ---
        with st.expander("🗺️ Mapa de Questões", expanded=False):
            # Agrupa por módulo
            grupos = {}
            for idx, q_item in enumerate(prov):
                grupo = st.session_state.prova_grupo_por_questao.get(q_item['id'], 'Outros')
                if grupo not in grupos:
                    grupos[grupo] = []
                grupos[grupo].append((idx, q_item))
            for grupo, lista in grupos.items():
                st.markdown(f"**{grupo}**")
                # Exibe em linhas de até 10 números
                for j in range(0, len(lista), 10):
                    cols = st.columns(10)
                    for k in range(10):
                        if j + k < len(lista):
                            idx, q_item = lista[j + k]
                            is_respondida = q_item['id'] in st.session_state.prova_respostas
                            is_atual = (idx == i)
                            label = str(idx + 1)
                            # Define a cor
                            if is_respondida:
                                color = "green"
                            else:
                                color = "red"
                            # Estilo do botão
                            btn_style = f"background-color: {color}; color: white;" if is_respondida else f"background-color: #ffcccc; color: black;"
                            if is_atual:
                                btn_style += " border: 3px solid yellow;"
                            cols[k].markdown(
                                f"""
                                <button style="{btn_style} padding: 5px 10px; border-radius: 5px; border: none; cursor: pointer;" 
                                        onclick="window.location.href='?prova_go={idx}'">
                                    {label}
                                </button>
                                """,
                                unsafe_allow_html=True
                            )
                            # Usar st.button com key única
                            # Não podemos usar onclick diretamente, vamos usar st.button
                            if cols[k].button(label, key=f"map_{idx}_{j+k}"):
                                st.session_state.prova_i = idx
                                st.rerun()
                st.divider()

        st.divider()
        card_questao(q, mostrar_objetivo=False, mostrar_destaque=True)

        resposta_prova = render_alternativas_com_descarte(q, f"prova_{q['id']}_{i}")

        if resposta_prova is not None:
            st.session_state.prova_respostas[q["id"]] = resposta_prova
            persistir_tudo()

        st.divider()
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("◀ Anterior", disabled=(i == 0), use_container_width=True):
                st.session_state.prova_i -= 1
                st.session_state.confirmar_finalizar = False
                persistir_tudo()
                st.rerun()

        with col2:
            if st.button("Próxima ▶", disabled=(i == len(prov) - 1), use_container_width=True):
                st.session_state.prova_i += 1
                st.session_state.confirmar_finalizar = False
                persistir_tudo()
                st.rerun()

        with col3:
            nao_resp_n = len(prov) - len(st.session_state.prova_respostas)
            if not st.session_state.confirmar_finalizar:
                if st.button("🏁 Finalizar", use_container_width=True):
                    if nao_resp_n > 0:
                        st.session_state.confirmar_finalizar = True
                        persistir_tudo()
                        st.rerun()
                    else:
                        st.session_state.prova_ativo = False
                        st.session_state.prova_finalizado = True
                        persistir_tudo()
                        st.rerun()
            else:
                if st.button("⚠️ Confirmar mesmo assim", use_container_width=True):
                    st.session_state.prova_ativo = False
                    st.session_state.prova_finalizado = True
                    st.session_state.confirmar_finalizar = False
                    persistir_tudo()
                    st.rerun()

        if st.session_state.confirmar_finalizar:
            st.warning(
                f"Você ainda tem **{nao_resp_n}** questão(ões) sem resposta. "
                "Confirme para encerrar ou navegue para respondê-las."
            )

    if st.session_state.prova_finalizado:
        prov = st.session_state.prova_questoes
        respostas = st.session_state.prova_respostas
        grupo_por_questao = st.session_state.prova_grupo_por_questao

        if not st.session_state.prova_registrado:
            for q_item in prov:
                registrar_resposta(q_item, respostas.get(q_item["id"]), "prova")
            st.session_state.prova_registrado = True
            persistir_tudo()
            
            duracao = int(time.time() - st.session_state.inicio_prova)
            respostas_prova = []
            for q_item in prov:
                respostas_prova.append({
                    'questao_id': q_item['id'],
                    'tema': q_item.get('tema', ''),
                    'codigo': q_item['codigo'],
                    'modulo': grupo_por_questao.get(q_item['id'], 'Outros'),
                    'resposta': respostas.get(q_item['id']),
                    'correta': q_item['correta']
                })
            prova_data = {
                'data': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'duracao_segundos': duracao,
                'total_questoes': len(prov),
                'total_acertos': sum(1 for q in prov if respostas.get(q['id']) == q['correta'])
            }
            db.salvar_prova(prova_data, respostas_prova)

        acertos_prov = sum(
            1 for q_item in prov
            if respostas.get(q_item["id"]) == q_item["correta"]
        )
        total_prov = len(prov)
        nao_resp = sum(1 for q_item in prov if respostas.get(q_item["id"]) is None)
        taxa_prov = acertos_prov / total_prov * 100 if total_prov else 0.0

        st.success("✅ Prova finalizada!")

        c1, c2, c3 = st.columns(3)
        c1.metric("Acertos", f"{acertos_prov}/{total_prov}")
        c2.metric("Taxa de acerto", f"{taxa_prov:.1f}%")
        c3.metric("Não respondidas", nao_resp)
        st.progress(taxa_prov / 100, text=f"Aproveitamento: {taxa_prov:.1f}%")

        st.divider()
        st.markdown("### 📊 RELATÓRIO DETALHADO POR MÓDULO")

        grupos_ids = {}
        for q_item in prov:
            grupo = grupo_por_questao.get(q_item["id"], "Outros")
            if grupo not in grupos_ids:
                grupos_ids[grupo] = []
            grupos_ids[grupo].append(q_item["id"])

        ordem_grupos = [g["nome"] for g in GRUPOS_PROVA]
        if "Outros" in grupos_ids and "Outros" not in ordem_grupos:
            ordem_grupos.append("Outros")

        dados_tabela = []
        for grupo in ordem_grupos:
            if grupo not in grupos_ids:
                continue
            ids_questoes = grupos_ids[grupo]
            total = len(ids_questoes)
            corretas_por_id = {q["id"]: q["correta"] for q in prov}
            acertos = sum(1 for qid in ids_questoes if respostas.get(qid) == corretas_por_id.get(qid))
            pct = (acertos / total * 100) if total else 0.0
            dados_tabela.append({
                "Módulo": grupo,
                "Total": total,
                "Acertos": acertos,
                "%": f"{pct:.1f}%"
            })

        if dados_tabela:
            df_rel = pd.DataFrame(dados_tabela)
            st.dataframe(
                df_rel.style.format({"Total": "{:.0f}", "Acertos": "{:.0f}"}),
                use_container_width=True,
                hide_index=True,
            )

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
                for q_item in prov:
                    render_correcao(q_item, respostas.get(q_item["id"]))

            with tabs[1]:
                lst = [q_item for q_item in prov if respostas.get(q_item["id"]) == q_item["correta"]]
                if lst:
                    for q_item in lst:
                        render_correcao(q_item, respostas.get(q_item["id"]))
                else:
                    st.info("Nenhum acerto.")

            with tabs[2]:
                lst = [
                    q_item for q_item in prov
                    if respostas.get(q_item["id"]) is not None
                    and respostas.get(q_item["id"]) != q_item["correta"]
                ]
                if lst:
                    for q_item in lst:
                        render_correcao(q_item, respostas.get(q_item["id"]))
                else:
                    st.info("Nenhum erro.")

            with tabs[3]:
                lst = [q_item for q_item in prov if respostas.get(q_item["id"]) is None]
                if lst:
                    for q_item in lst:
                        render_correcao(q_item, None)
                else:
                    st.info("Todas as questões foram respondidas.")

        if st.button("🔄 Nova Prova", use_container_width=True):
            resetar_prova()
            st.rerun()

# =======================================================
# MODO 5 — Histórico de Provas
# =======================================================
elif modo == "Histórico de Provas":
    st.subheader("📚 Histórico de Provas Realizadas")
    
    provas = db.carregar_provas()
    if not provas:
        st.info("Nenhuma prova realizada ainda. Complete uma prova para ver o histórico.")
        st.stop()
    
    mapa_questoes = {q['id']: q for q in questoes}
    
    for prova in provas:
        data_str = datetime.strptime(prova['data'], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
        duracao = prova['duracao_segundos']
        minutos = duracao // 60
        segundos = duracao % 60
        with st.expander(f"📅 {data_str}  |  {prova['total_acertos']}/{prova['total_questoes']} acertos  |  ⏱️ {minutos}m {segundos}s"):
            respostas = db.carregar_respostas_prova(prova['id'])
            if not respostas:
                st.warning("Detalhes não disponíveis.")
            else:
                st.markdown("**Correção detalhada:**")
                for resp in respostas:
                    q = mapa_questoes.get(resp['questao_id'])
                    correto = (resp['resposta'] == resp['correta'])
                    num = resp['questao_id']
                    if q:
                        with st.expander(f"Q{num} — {resp['codigo']} ({'✅ Correto' if correto else '❌ Errado'})"):
                            card_questao(q, mostrar_objetivo=False, mostrar_destaque=False)
                            if resp['resposta'] is not None:
                                resp_texto = q['opcoes'].get(resp['resposta'], resp['resposta'])
                                st.markdown(f"**Sua resposta:** {resp['resposta']}) {resp_texto}")
                            else:
                                st.markdown("**Sua resposta:** *Não respondida*")
                            corr_texto = q['opcoes'].get(resp['correta'], resp['correta'])
                            st.markdown(f"**Resposta correta:** {resp['correta']}) {corr_texto}")
                            if not correto and resp['resposta'] is not None:
                                st.markdown(f"**Explicação:** {q.get('explicacao', 'Sem explicação.')}")
                    else:
                        if correto:
                            st.success(f"✅ Q{num} — {resp['codigo']}: correto ({resp['resposta']})")
                        else:
                            st.error(f"❌ Q{num} — {resp['codigo']}: marcou **{resp['resposta']}** | correta: **{resp['correta']}**")
                st.markdown("**Desempenho por módulo:**")
                modulos = {}
                for resp in respostas:
                    modulo = resp['modulo']
                    if modulo not in modulos:
                        modulos[modulo] = {'total': 0, 'acertos': 0}
                    modulos[modulo]['total'] += 1
                    if resp['resposta'] == resp['correta']:
                        modulos[modulo]['acertos'] += 1
                for modulo, dados in modulos.items():
                    pct = dados['acertos'] / dados['total'] * 100 if dados['total'] else 0
                    st.write(f"- {modulo}: {dados['acertos']}/{dados['total']} ({pct:.1f}%)")

# =======================================================
# MODO 6 — Questões Destacadas (com resposta interativa)
# =======================================================
elif modo == "Questões Destacadas":
    st.subheader("⭐ Revisão de Questões Destacadas")
    
    if not st.session_state.destacadas:
        st.info("Nenhuma questão destacada. Marque questões com o botão ⭐ durante os estudos.")
        st.stop()
    
    # Preparar lista de questões (apenas uma vez por sessão)
    if not st.session_state.destacada_lista:
        mapa = {q['id']: q for q in questoes}
        questions = [mapa[qid] for qid in st.session_state.destacadas if qid in mapa]
        if not questions:
            st.info("As questões destacadas não foram encontradas no banco.")
            st.stop()
        st.session_state.destacada_lista = questions
        random.shuffle(st.session_state.destacada_lista)
        st.session_state.destacada_i = 0
        st.session_state.destacada_respondido = False
        st.session_state.destacada_resposta = None
    
    total = len(st.session_state.destacada_lista)
    i = st.session_state.destacada_i
    
    if i >= total:
        st.success("🎉 Você revisou todas as questões destacadas!")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Recomeçar", use_container_width=True):
                resetar_destacada()
                st.rerun()
        with col2:
            if st.button("🗑️ Limpar lista", use_container_width=True):
                st.session_state.destacada_lista = []
                st.session_state.destacada_i = 0
                st.rerun()
        st.stop()
    
    q = st.session_state.destacada_lista[i]
    
    # Progresso
    st.progress((i + 1) / total, text=f"Questão {i+1} de {total}")
    
    st.divider()
    card_questao(q, mostrar_objetivo=True, mostrar_destaque=True)
    
    # Alternativas interativas (radio simples, sem descarte)
    opcoes = list(q['opcoes'].keys())
    resposta_key = f"destacada_{q['id']}"
    if resposta_key not in st.session_state:
        st.session_state[resposta_key] = None
    
    selected = st.radio(
        "Escolha uma alternativa:",
        opcoes,
        format_func=lambda x: f"{x}) {q['opcoes'][x]}",
        key=f"radio_dest_{q['id']}_{i}",
        index=None
    )
    st.session_state[resposta_key] = selected
    
    if not st.session_state.destacada_respondido:
        if st.button("✅ Responder", use_container_width=True):
            if selected is None:
                st.warning("Selecione uma alternativa.")
            else:
                st.session_state.destacada_resposta = selected
                st.session_state.destacada_respondido = True
                # Registrar resposta (apenas para estatística, não entra nos erros)
                # Opcional: podemos chamar registrar_resposta com origem="destacada"
                # Para não poluir o histórico, podemos apenas mostrar o resultado
                st.rerun()
    else:
        # Mostrar resultado
        correto = (st.session_state.destacada_resposta == q["correta"])
        if correto:
            st.success("✅ Correto!")
        else:
            st.error(f"❌ Errado — correta: **{q['correta']}**) {q['opcoes'][q['correta']]}")
        with st.expander("Ver explicação", expanded=True):
            st.write(q.get("explicacao", "Sem explicação disponível."))
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➡️ Próxima", use_container_width=True):
                st.session_state.destacada_i += 1
                st.session_state.destacada_respondido = False
                st.session_state.destacada_resposta = None
                st.rerun()
        with col2:
            if st.button("⭐ Remover destaque", use_container_width=True):
                toggle_destaque(q['id'])
                # Remover da lista atual
                st.session_state.destacada_lista = [item for item in st.session_state.destacada_lista if item['id'] != q['id']]
                # Ajustar índice se necessário
                if st.session_state.destacada_i >= len(st.session_state.destacada_lista):
                    st.session_state.destacada_i = max(0, len(st.session_state.destacada_lista) - 1)
                st.session_state.destacada_respondido = False
                st.session_state.destacada_resposta = None
                st.rerun()

# =======================================================
# MODO 7 — Dashboard
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
