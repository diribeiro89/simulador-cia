import streamlit as st
import json
import random
import time
from datetime import datetime, timedelta
import pandas as pd
import database_supabase as db

st.set_page_config(
    page_title="Simulador CGA",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# -------------------------------------------------------
# Carregar bancos
# -------------------------------------------------------
@st.cache_data
def carregar_bancos():
    arquivos = {
        "Banco Principal": "questoes_cga_todos_temas.json",
        "Simulado 1": "simulado_1_completo.json",
        "Simulado 2": "simulado_2_completo.json",
        "Simulado 3": "simulado_3_completo.json",
        "Simulado 4": "simulado_4_completo.json",
    }
    bancos = {}
    offset = {
        "Banco Principal": 0,
        "Simulado 1": 10000,
        "Simulado 2": 20000,
        "Simulado 3": 30000,
        "Simulado 4": 40000,
    }
    for nome, caminho in arquivos.items():
        try:
            with open(caminho, encoding="utf-8") as f:
                questoes = json.load(f)
            for i, q in enumerate(questoes):
                novo_id = offset[nome] + (q.get("id", i + 1))
                q["id_unico"] = novo_id
                q["fonte"] = nome
            bancos[nome] = questoes
        except FileNotFoundError:
            bancos[nome] = []
            st.warning(f"Arquivo {caminho} não encontrado. Banco '{nome}' vazio.")
    return bancos

bancos = carregar_bancos()

# -------------------------------------------------------
# Funções auxiliares (definidas ANTES de inicializar estado)
# -------------------------------------------------------
def questoes_para_erros():
    todas = []
    for lista in bancos.values():
        todas.extend(lista)
    return todas

def questoes_buscadas():
    fonte = st.session_state.get("fonte_atual", "Banco Principal")
    return bancos.get(fonte, [])

def obter_temas():
    todos = set()
    for lista in bancos.values():
        for q in lista:
            if q.get("tema"):
                todos.add(q["tema"])
    return sorted(todos)

# -------------------------------------------------------
# Configuração da Prova
# -------------------------------------------------------
GRUPOS_PROVA = [
    {"nome": "Gestão de Carteiras – Renda Variável", "temas_json": ["CGA - Gestão de Carteiras Renda Variável"], "proporcao": 20},
    {"nome": "Gestão de Carteiras – Renda Fixa", "temas_json": ["CGA - Gestão de Carteiras - Renda Fixa"], "proporcao": 20},
    {"nome": "Investimentos no Exterior", "temas_json": ["CGA - Investimentos no Exterior"], "proporcao": 13},
    {"nome": "Avaliação de Desempenho", "temas_json": ["CGA - Avaliação de Desempenho"], "proporcao": 13},
    {"nome": "Gestão de Risco", "temas_json": ["CGA - Gestão de Investimentos e de Risco"], "proporcao": 13},
    {"nome": "Legislação, Regulação e Tributação", "temas_json": ["CGA - Legislação, Regulação e Melhores Práticas", "CGA - Tributação de Fundos de Investimento"], "proporcao": 21, "subproporcoes": [11, 10]}
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
                distribuicao.append({"grupo_nome": grupo["nome"], "tema_json": tema, "quantidade": qtd_tema})
            diff = qtd_grupo - sum(item["quantidade"] for item in distribuicao if item["grupo_nome"] == grupo["nome"])
            if diff != 0:
                for item in distribuicao:
                    if item["grupo_nome"] == grupo["nome"]:
                        item["quantidade"] += diff
                        break
        else:
            distribuicao.append({"grupo_nome": grupo["nome"], "tema_json": grupo["temas_json"][0], "quantidade": qtd_grupo})
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
        "fonte_atual": "Banco Principal",
        "questao_atual": None,
        "respondido": False,
        "resposta_usuario": None,
        "historico": [],
        "erros": [],
        "acertos": [],
        "simulados_estados": {},
        "revisao_lista": [],
        "revisao_i": 0,
        "revisao_concluida": False,
        "revisao_respondido": False,
        "revisao_resposta": None,
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
        "destacadas": db.carregar_destacadas(),
        "confirmar_zerar": False,
        "destacada_lista": [],
        "destacada_i": 0,
        "destacada_respondido": False,
        "destacada_resposta": None,
        "busca_codigo": "",
        "busca_questao": None,
        "busca_respondido": False,
        "busca_resposta": None,
        "sim_personalizado": {
            "questoes": [], "respostas": {}, "i": 0, "ativo": False, "finalizado": False,
            "registrado": False, "inicio": None, "duracao_min": 180, "confirmar_finalizar": False,
        },
        "em_simulado": False,
        "respostas_pendentes": [],
        "estatisticas_questoes": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    for k, v in estado_salvo.items():
        if k in st.session_state:
            st.session_state[k] = v
    st.session_state.historico = db.load_historico()
    st.session_state.erros = db.load_erros(questoes_para_erros())
    st.session_state.leitner = db.load_leitner()
    st.session_state.alternativas_descartadas = db.load_descartes()
    st.session_state.destacadas = db.carregar_destacadas()
    
    # Tenta carregar estatísticas, mas se falhar, mantém vazio
    try:
        st.session_state.estatisticas_questoes = db.carregar_estatisticas_questoes()
    except Exception:
        st.session_state.estatisticas_questoes = {}
    
    modos_validos = ["Treino livre", "Revisar erros", "Simulado", "Prova", "Histórico de Provas", "Questões Destacadas", "Buscar Questão", "Dashboard"]
    if st.session_state.modo not in modos_validos:
        st.session_state.modo = "Treino livre"
    fontes_validas = list(bancos.keys())
    if st.session_state.fonte_atual not in fontes_validas:
        st.session_state.fonte_atual = "Banco Principal"

inicializar_estado()

# -------------------------------------------------------
# Funções de resposta e estatísticas
# -------------------------------------------------------
def adicionar_erro_sem_duplicar(q):
    qid = q.get("id_unico", q["id"])
    ids = {e.get("id_unico", e["id"]) for e in st.session_state.erros}
    if qid not in ids:
        st.session_state.erros.append(q)
        persistir_tudo()

def remover_erro(q):
    qid = q.get("id_unico", q["id"])
    st.session_state.erros = [e for e in st.session_state.erros if e.get("id_unico", e["id"]) != qid]
    persistir_tudo()

def atualizar_estatistica_questao(qid, acertou):
    if qid not in st.session_state.estatisticas_questoes:
        st.session_state.estatisticas_questoes[qid] = {"acertos": 0, "erros": 0, "total": 0}
    if acertou:
        st.session_state.estatisticas_questoes[qid]["acertos"] += 1
    else:
        st.session_state.estatisticas_questoes[qid]["erros"] += 1
    st.session_state.estatisticas_questoes[qid]["total"] += 1
    try:
        db.atualizar_estatistica_questao(qid, acertou)
    except Exception:
        pass

def registrar_resposta(q, resposta, origem="treino", salvar_imediato=True):
    qid = q.get("id_unico", q["id"])
    correto = (resposta is not None) and (resposta == q["correta"])
    if origem == "revisao_erros":
        dados = st.session_state.leitner.get(qid, {'nivel': 1, 'proxima': None})
        nivel_atual = dados['nivel']
        if correto:
            novo_nivel = min(nivel_atual + 1, 5)
        else:
            novo_nivel = max(nivel_atual - 1, 1)
        dias = {1:1, 2:3, 3:7, 4:15, 5:30}[novo_nivel]
        proxima = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
        st.session_state.leitner[qid] = {'nivel': novo_nivel, 'proxima': proxima}
    
    atualizar_estatistica_questao(qid, correto)
    
    registro = {
        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "id": qid,
        "id_original": q.get("id"),
        "numero_original": q.get("numero_original"),
        "tema": q.get("tema"),
        "codigo": q["codigo"],
        "objetivo": q.get("objetivo"),
        "resposta": resposta,
        "correta": q["correta"],
        "acertou": correto,
        "origem": origem,
        "fonte": q.get("fonte", ""),
    }
    st.session_state.historico.append(registro)
    if correto:
        st.session_state.acertos.append(qid)
        if origem == "revisao_erros":
            remover_erro(q)
    else:
        adicionar_erro_sem_duplicar(q)
    if salvar_imediato:
        persistir_tudo()
    return correto

# -------------------------------------------------------
# UI Helpers
# -------------------------------------------------------
def card_questao(q, mostrar_objetivo=True, mostrar_destaque=False):
    qid = q.get("id_unico", q["id"])
    num = q.get("numero_original", qid)
    cols = st.columns([1, 0.1]) if mostrar_destaque else st.columns([1])
    with cols[0]:
        st.markdown(f"### Questão {num} — {q['codigo']} | V. {q['versao']} | {q.get('fonte', '')}")
    if mostrar_destaque:
        with cols[1]:
            is_dest = qid in st.session_state.destacadas
            if st.button("⭐" if is_dest else "☆", key=f"dest_{qid}"):
                if is_dest:
                    st.session_state.destacadas.remove(qid)
                    db.remover_destacada(qid)
                else:
                    st.session_state.destacadas.add(qid)
                    db.adicionar_destacada(qid)
                st.rerun()
    if q.get("tema"):
        st.caption(f"📂 {q['tema']}")
    if mostrar_objetivo and q.get("objetivo"):
        with st.expander("Objetivo da questão"):
            st.write(q["objetivo"])
    st.markdown(q["pergunta"])

def render_alternativas_com_descarte(q, key_prefix):
    qid = q.get("id_unico", q["id"])
    descartadas = st.session_state.alternativas_descartadas.get(qid, [])
    opcoes = list(q['opcoes'].keys())
    resposta_key = f"resposta_{qid}_{key_prefix}"
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
                        <div style="background-color:#0d3b0d; color:#9aff9a; padding:8px 12px; border-radius:8px; border:1px solid #2a7a2a; font-weight:bold; cursor:default;">
                        {label}
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    if st.button(label, key=f"sel_{qid}_{letra}_{key_prefix}", use_container_width=True):
                        st.session_state[resposta_key] = letra
                        st.rerun()
        with col2:
            btn_label = "↩️" if is_descartada else "✖️"
            if st.button(btn_label, key=f"desc_{qid}_{letra}_{key_prefix}"):
                if letra in descartadas:
                    descartadas.remove(letra)
                else:
                    descartadas.append(letra)
                st.session_state.alternativas_descartadas[qid] = descartadas
                if st.session_state[resposta_key] == letra:
                    st.session_state[resposta_key] = None
                persistir_tudo()
                st.rerun()
    return st.session_state[resposta_key]

def mostrar_resultado(q, resposta):
    if resposta == q["correta"]:
        st.success("✅ Correto!")
    else:
        st.error(f"❌ Errado — correta: **{q['correta']}**) {q['opcoes'][q['correta']]}")
    with st.expander("Ver explicação", expanded=True):
        st.write(q.get("explicacao", "Sem explicação disponível."))

def estatisticas():
    total = len(st.session_state.historico)
    acertos_n = sum(1 for h in st.session_state.historico if h["acertou"])
    erros_n = total - acertos_n
    taxa = (acertos_n / total * 100) if total else 0.0
    return total, acertos_n, erros_n, taxa

LABEL_ORIGEM = {"treino": "Treino livre", "revisao_erros": "Revisão de erros", "simulado": "Simulado", "prova": "Prova ANBIMA"}

def escolher_questao(lista=None):
    base = lista if lista else questoes_buscadas()
    return random.choice(base) if base else None

def filtrar_base(tema="Todos", objetivo="Todos"):
    base = questoes_buscadas()
    if tema != "Todos":
        base = [q for q in base if q.get("tema") == tema]
    if objetivo != "Todos":
        base = [q for q in base if q.get("objetivo") == objetivo]
    return base

# -------------------------------------------------------
# Renderização de simulado
# -------------------------------------------------------
def render_simulado(nome_simulado, fonte_questoes, estado_key=None, is_personalizado=False):
    if is_personalizado:
        estado = st.session_state.sim_personalizado
    else:
        if nome_simulado not in st.session_state.simulados_estados:
            st.session_state.simulados_estados[nome_simulado] = {
                "questoes": [], "respostas": {}, "i": 0, "ativo": False, "finalizado": False,
                "registrado": False, "inicio": None, "duracao_min": 180, "confirmar_finalizar": False,
            }
        estado = st.session_state.simulados_estados[nome_simulado]

    if not estado["ativo"] and not estado["finalizado"]:
        base_sim = fonte_questoes
        if not base_sim:
            st.warning(f"Nenhuma questão disponível para {nome_simulado}.")
            return
        if is_personalizado:
            temas_sim = ["Todos"] + sorted({q.get("tema") for q in base_sim if q.get("tema")})
            filtro_tema_sim = st.selectbox("Filtrar por tema", temas_sim, key=f"filtro_tema_personalizado")
            if filtro_tema_sim != "Todos":
                base_sim = [q for q in base_sim if q.get("tema") == filtro_tema_sim]
            if not base_sim:
                st.warning("Nenhuma questão para o tema selecionado.")
                return
        col1, col2 = st.columns(2)
        max_qtd = len(base_sim)
        qtd = col1.number_input(
            "Quantidade de questões",
            min_value=5, max_value=max_qtd, value=min(max_qtd, 45), step=5,
            key=f"qtd_{nome_simulado}_{estado_key if estado_key else ''}"
        )
        duracao = col2.number_input(
            "Tempo em minutos",
            min_value=10, max_value=240, value=180, step=10,
            key=f"dur_{nome_simulado}_{estado_key if estado_key else ''}"
        )
        st.info(f"📋 **{int(qtd)} questões** &nbsp;|&nbsp; ⏱️ **{int(duracao)} min** &nbsp;|&nbsp; Base disponível: **{len(base_sim)} questões**")
        if st.button("🚀 Iniciar", use_container_width=True, key=f"iniciar_{nome_simulado}_{estado_key if estado_key else ''}"):
            qtd_real = int(min(qtd, len(base_sim)))
            selecionadas = random.sample(base_sim, qtd_real)
            estado["questoes"] = selecionadas
            estado["respostas"] = {}
            estado["i"] = 0
            estado["ativo"] = True
            estado["finalizado"] = False
            estado["registrado"] = False
            estado["inicio"] = time.time()
            estado["duracao_min"] = int(duracao)
            estado["confirmar_finalizar"] = False
            st.session_state.em_simulado = True
            st.session_state.respostas_pendentes = []
            st.rerun()
        return

    if estado["ativo"]:
        elapsed = time.time() - estado["inicio"]
        restante = max(0.0, estado["duracao_min"] * 60 - elapsed)
        if restante <= 0:
            st.warning("⏰ Tempo encerrado. Finalizando automaticamente.")
            estado["ativo"] = False
            estado["finalizado"] = True
            st.session_state.em_simulado = False
            for reg in st.session_state.respostas_pendentes:
                registrar_resposta(reg["q"], reg["resp"], origem="simulado", salvar_imediato=False)
            st.session_state.respostas_pendentes = []
            persistir_tudo()
            salvar_historico_simulado(estado, nome_simulado)
            st.rerun()
        min_rest = int(restante // 60)
        seg_rest = int(restante % 60)
        questoes = estado["questoes"]
        i = estado["i"]
        q = questoes[i]
        col_timer, col_prog = st.columns([1, 3])
        col_timer.metric("⏱️ Tempo restante", f"{min_rest:02d}:{seg_rest:02d}")
        with col_prog:
            respondidas_n = len(estado["respostas"])
            st.progress((i + 1) / len(questoes), text=f"Questão {i+1} de {len(questoes)} | {respondidas_n} respondidas")
        st.divider()
        card_questao(q, mostrar_objetivo=False, mostrar_destaque=True)
        resposta_sim = render_alternativas_com_descarte(q, f"{nome_simulado}_{q.get('id_unico', q['id'])}_{i}")
        if resposta_sim is not None:
            estado["respostas"][q.get("id_unico", q["id"])] = resposta_sim
            st.session_state.respostas_pendentes.append({"q": q, "resp": resposta_sim})
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("◀ Anterior", disabled=(i == 0), use_container_width=True, key=f"prev_{nome_simulado}_{estado_key if estado_key else ''}"):
                estado["i"] -= 1
                estado["confirmar_finalizar"] = False
                st.rerun()
        with col2:
            if st.button("Próxima ▶", disabled=(i == len(questoes) - 1), use_container_width=True, key=f"next_{nome_simulado}_{estado_key if estado_key else ''}"):
                estado["i"] += 1
                estado["confirmar_finalizar"] = False
                st.rerun()
        with col3:
            nao_resp_n = len(questoes) - len(estado["respostas"])
            if not estado["confirmar_finalizar"]:
                if st.button("🏁 Finalizar", use_container_width=True, key=f"finish_{nome_simulado}_{estado_key if estado_key else ''}"):
                    if nao_resp_n > 0:
                        estado["confirmar_finalizar"] = True
                        st.rerun()
                    else:
                        estado["ativo"] = False
                        estado["finalizado"] = True
                        st.session_state.em_simulado = False
                        for reg in st.session_state.respostas_pendentes:
                            registrar_resposta(reg["q"], reg["resp"], origem="simulado", salvar_imediato=False)
                        st.session_state.respostas_pendentes = []
                        persistir_tudo()
                        salvar_historico_simulado(estado, nome_simulado)
                        st.rerun()
            else:
                if st.button("⚠️ Confirmar mesmo assim", use_container_width=True, key=f"confirm_{nome_simulado}_{estado_key if estado_key else ''}"):
                    estado["ativo"] = False
                    estado["finalizado"] = True
                    estado["confirmar_finalizar"] = False
                    st.session_state.em_simulado = False
                    for reg in st.session_state.respostas_pendentes:
                        registrar_resposta(reg["q"], reg["resp"], origem="simulado", salvar_imediato=False)
                    st.session_state.respostas_pendentes = []
                    persistir_tudo()
                    salvar_historico_simulado(estado, nome_simulado)
                    st.rerun()
        if estado["confirmar_finalizar"]:
            st.warning(f"Você ainda tem **{nao_resp_n}** questão(ões) sem resposta. Confirme para encerrar ou navegue para respondê-las.")
        return

    if estado["finalizado"]:
        questoes = estado["questoes"]
        respostas = estado["respostas"]
        if not estado["registrado"]:
            estado["registrado"] = True
            persistir_tudo()
        acertos = sum(1 for q in questoes if respostas.get(q.get("id_unico", q["id"])) == q["correta"])
        total = len(questoes)
        nao_resp = sum(1 for q in questoes if respostas.get(q.get("id_unico", q["id"])) is None)
        taxa = acertos / total * 100 if total else 0.0
        st.success(f"✅ {nome_simulado} finalizado!")
        c1, c2, c3 = st.columns(3)
        c1.metric("Acertos", f"{acertos}/{total}")
        c2.metric("Taxa de acerto", f"{taxa:.1f}%")
        c3.metric("Não respondidas", nao_resp)
        st.progress(taxa / 100, text=f"Aproveitamento: {taxa:.1f}%")
        with st.expander("📋 Ver correção completa", expanded=False):
            def render_correcao(q_item, resp):
                num = q_item.get("numero_original", q_item.get("id_unico", q_item["id"]))
                correto = (resp is not None) and (resp == q_item["correta"])
                nao_respondida = resp is None
                if correto:
                    st.success(f"✅ Q{num} — {q_item['codigo']}: correto ({resp})")
                elif nao_respondida:
                    st.warning(f"⚠️ Q{num} — {q_item['codigo']}: não respondida | correta: **{q_item['correta']}**")
                else:
                    st.error(f"❌ Q{num} — {q_item['codigo']}: você marcou **{resp}** | correta: **{q_item['correta']}**")
                with st.expander(f"Explicação — {q_item['codigo']}"):
                    st.write(q_item.get("explicacao", "Sem explicação disponível."))
            tabs = st.tabs(["Todas", "✅ Acertos", "❌ Erros", "⚠️ Não respondidas"])
            with tabs[0]:
                for q_item in questoes:
                    render_correcao(q_item, respostas.get(q_item.get("id_unico", q_item["id"])))
            with tabs[1]:
                lst = [q for q in questoes if respostas.get(q.get("id_unico", q["id"])) == q["correta"]]
                if lst:
                    for q_item in lst:
                        render_correcao(q_item, respostas.get(q_item.get("id_unico", q_item["id"])))
                else:
                    st.info("Nenhum acerto.")
            with tabs[2]:
                lst = [q for q in questoes if respostas.get(q.get("id_unico", q["id"])) is not None and respostas.get(q.get("id_unico", q["id"])) != q["correta"]]
                if lst:
                    for q_item in lst:
                        render_correcao(q_item, respostas.get(q_item.get("id_unico", q_item["id"])))
                else:
                    st.info("Nenhum erro.")
            with tabs[3]:
                lst = [q for q in questoes if respostas.get(q.get("id_unico", q["id"])) is None]
                if lst:
                    for q_item in lst:
                        render_correcao(q_item, None)
                else:
                    st.info("Todas as questões foram respondidas.")
        if st.button(f"🔄 Novo {nome_simulado}", use_container_width=True, key=f"novo_{nome_simulado}_{estado_key if estado_key else ''}"):
            if is_personalizado:
                resetar_personalizado()
            else:
                resetar_simulado_estado(nome_simulado)
            st.session_state.em_simulado = False
            st.session_state.respostas_pendentes = []
            st.rerun()

def salvar_historico_simulado(estado, nome_simulado):
    questoes = estado["questoes"]
    respostas = estado["respostas"]
    acertos = sum(1 for q in questoes if respostas.get(q.get("id_unico", q["id"])) == q["correta"])
    total = len(questoes)
    nao_resp = sum(1 for q in questoes if respostas.get(q.get("id_unico", q["id"])) is None)
    tempo = int(time.time() - estado["inicio"])
    detalhes = []
    for q in questoes:
        qid = q.get("id_unico", q["id"])
        detalhes.append({
            'questao_id': qid,
            'resposta': respostas.get(qid),
            'correta': q["correta"],
            'tema': q.get("tema", ""),
            'codigo': q["codigo"],
            'fonte': q.get("fonte", ""),
        })
    db.salvar_simulado_historico({
        'data': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'fonte': nome_simulado,
        'total_questoes': total,
        'acertos': acertos,
        'nao_respondidas': nao_resp,
        'tempo_segundos': tempo,
    }, detalhes)

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
    st.session_state.revisao_respondido = False
    st.session_state.revisao_resposta = None
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

def resetar_busca():
    st.session_state.busca_codigo = ""
    st.session_state.busca_questao = None
    st.session_state.busca_respondido = False
    st.session_state.busca_resposta = None

def resetar_simulado_estado(nome_simulado):
    if nome_simulado in st.session_state.simulados_estados:
        del st.session_state.simulados_estados[nome_simulado]

def resetar_todos_simulados():
    st.session_state.simulados_estados = {}

def resetar_personalizado():
    st.session_state.sim_personalizado = {
        "questoes": [], "respostas": {}, "i": 0, "ativo": False, "finalizado": False,
        "registrado": False, "inicio": None, "duracao_min": 180, "confirmar_finalizar": False,
    }

# -------------------------------------------------------
# Sidebar
# -------------------------------------------------------
st.sidebar.title("📚 Simulador CGA")
fontes_disponiveis = [nome for nome, lista in bancos.items() if lista]
fonte_selecionada = st.sidebar.selectbox(
    "Fonte de questões (Treino/Revisão/Prova)",
    fontes_disponiveis,
    index=fontes_disponiveis.index(st.session_state.fonte_atual) if st.session_state.fonte_atual in fontes_disponiveis else 0,
)
if fonte_selecionada != st.session_state.fonte_atual:
    st.session_state.fonte_atual = fonte_selecionada
    resetar_treino()
    persistir_tudo()
    st.rerun()

modo_options = ["Treino livre", "Revisar erros", "Simulado", "Prova", "Histórico de Provas", "Questões Destacadas", "Buscar Questão", "Dashboard"]
modo = st.sidebar.radio(
    "Modo de estudo",
    modo_options,
    index=modo_options.index(st.session_state.modo) if st.session_state.modo in modo_options else 0,
)
if modo != st.session_state.modo:
    st.session_state.modo = modo
    if modo == "Questões Destacadas":
        resetar_destacada()
    elif modo == "Buscar Questão":
        resetar_busca()
    elif modo == "Simulado":
        pass
    resetar_treino()
    persistir_tudo()
    st.rerun()

total_h, acertos_h, erros_h, taxa_h = estatisticas()
st.sidebar.metric("Questões respondidas", total_h)
st.sidebar.metric("Taxa de acerto", f"{taxa_h:.1f}%")
st.sidebar.metric("Erros salvos", len(st.session_state.erros))
st.sidebar.metric("⭐ Destacadas", len(st.session_state.destacadas))
st.sidebar.divider()
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
                    resetar_prova()
                    resetar_destacada()
                    resetar_busca()
                    resetar_todos_simulados()
                    resetar_personalizado()
                    db.save_historico([])
                    db.save_estado(st.session_state)
                    db.limpar_provas()
                    db.limpar_destacadas()
                    db.limpar_simulados_historico()
                    st.session_state.confirmar_zerar = False
                    st.success("✅ Histórico zerado com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Senha incorreta. Tente novamente.")
        with col2:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state.confirmar_zerar = False
                st.rerun()
st.sidebar.divider()
st.sidebar.caption(f"Fonte atual: {st.session_state.fonte_atual}")

# -------------------------------------------------------
# Modos principais
# -------------------------------------------------------
temas = obter_temas()

# =======================================================
# MODO 1 — Treino livre
# =======================================================
if modo == "Treino livre":
    st.subheader("Treino livre")
    filtro_tema = st.selectbox("Filtrar por tema", ["Todos"] + temas)
    objetivos_disp = sorted({q.get("objetivo") for q in questoes_buscadas() if q.get("objetivo") and (filtro_tema == "Todos" or q.get("tema") == filtro_tema)})
    filtro_objetivo = st.selectbox("Filtrar por objetivo", ["Todos"] + objetivos_disp)
    base = filtrar_base(filtro_tema, filtro_objetivo)
    if (filtro_tema != st.session_state.filtro_tema_atual or filtro_objetivo != st.session_state.filtro_objetivo_atual) or (st.session_state.questao_atual not in base):
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
    resposta = render_alternativas_com_descarte(q, f"treino_{q.get('id_unico', q['id'])}")
    if not st.session_state.respondido:
        if st.button("✅ Responder", use_container_width=True):
            if resposta is None:
                st.warning("Selecione uma alternativa antes de responder.")
            else:
                st.session_state.resposta_usuario = resposta
                st.session_state.respondido = True
                registrar_resposta(q, resposta, "treino", salvar_imediato=True)
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
    st.subheader("Revisar erros (Leitner)")

    # Inicializa a lista de revisão (se vazia)
    if not st.session_state.revisao_lista:
        questoes_revisar = []
        hoje = datetime.now().strftime("%Y-%m-%d")
        for qid, dados in st.session_state.leitner.items():
            if dados['proxima'] and dados['proxima'] <= hoje:
                questoes_revisar.append(qid)
        if questoes_revisar:
            todas = []
            for lista in bancos.values():
                todas.extend(lista)
            mapa = {q['id_unico']: q for q in todas}
            st.session_state.revisao_lista = [mapa[qid] for qid in questoes_revisar if qid in mapa]
        else:
            st.session_state.revisao_lista = st.session_state.erros.copy()
        random.shuffle(st.session_state.revisao_lista)
        st.session_state.revisao_i = 0
        st.session_state.revisao_respondido = False
        st.session_state.revisao_resposta = None

    if not st.session_state.revisao_lista:
        st.info("Você não tem erros salvos ou agendados para revisar.")
        st.stop()

    total_rev = len(st.session_state.revisao_lista)
    i_rev = st.session_state.revisao_i

    # Navegação
    col_prev, col_pos, col_info = st.columns([1, 1, 2])
    with col_prev:
        if st.button("◀ Anterior", disabled=(i_rev == 0), use_container_width=True):
            st.session_state.revisao_i -= 1
            st.session_state.revisao_respondido = False
            st.session_state.revisao_resposta = None
            st.rerun()
    with col_pos:
        if st.button("Próxima ▶", disabled=(i_rev >= total_rev - 1), use_container_width=True):
            st.session_state.revisao_i += 1
            st.session_state.revisao_respondido = False
            st.session_state.revisao_resposta = None
            st.rerun()
    with col_info:
        st.caption(f"Questão {i_rev + 1} de {total_rev}")

    q = st.session_state.revisao_lista[i_rev]
    st.divider()
    card_questao(q, mostrar_destaque=True)

    # --- RADIO COM DESCARTA (sem recarga ao selecionar) ---
    qid = q.get("id_unico", q["id"])
    descartadas = st.session_state.alternativas_descartadas.get(qid, [])
    opcoes = list(q['opcoes'].keys())
    
    # Exibe alternativas riscadas e botões de restauração
    st.markdown("**Alternativas:**")
    # Mostra as não descartadas primeiro (no radio) e as descartadas depois (riscadas)
    opcoes_validas = [letra for letra in opcoes if letra not in descartadas]
    
    # Se houver descartadas, exibe com botão de restaurar
    if descartadas:
        st.markdown("**Alternativas descartadas (clique em ↩️ para restaurar):**")
        for letra in descartadas:
            col1, col2 = st.columns([0.85, 0.15])
            with col1:
                st.markdown(f"~~{letra}) {q['opcoes'][letra]}~~")
            with col2:
                if st.button("↩️", key=f"restore_rev_{qid}_{letra}_{i_rev}"):
                    descartadas.remove(letra)
                    st.session_state.alternativas_descartadas[qid] = descartadas
                    persistir_tudo()
                    st.rerun()
        st.divider()

    # Radio para seleção (apenas opções válidas)
    resposta_atual = st.session_state.revisao_resposta if st.session_state.revisao_respondido else None
    default_index = None
    if resposta_atual in opcoes_validas:
        default_index = opcoes_validas.index(resposta_atual)

    if opcoes_validas:
        selected = st.radio(
            "Escolha uma alternativa:",
            opcoes_validas,
            format_func=lambda x: f"{x}) {q['opcoes'][x]}",
            key=f"radio_rev_{qid}_{i_rev}",
            index=default_index,
            disabled=st.session_state.revisao_respondido
        )
    else:
        selected = None
        st.warning("Todas as alternativas foram descartadas! Restaure alguma para responder.")

    # Armazena a seleção (sem recarregar)
    if not st.session_state.revisao_respondido and selected is not None:
        st.session_state.revisao_resposta = selected

    # Botão Responder
    if not st.session_state.revisao_respondido:
        if st.button("✅ Responder", use_container_width=True):
            if st.session_state.revisao_resposta is None:
                st.warning("Selecione uma alternativa antes de responder.")
            else:
                st.session_state.revisao_respondido = True
                registrar_resposta(q, st.session_state.revisao_resposta, "revisao_erros", salvar_imediato=True)
                st.rerun()
    else:
        mostrar_resultado(q, st.session_state.revisao_resposta)
        if st.button("🔄 Avançar", use_container_width=True):
            st.session_state.revisao_respondido = False
            st.session_state.revisao_resposta = None
            if i_rev < total_rev - 1:
                st.session_state.revisao_i += 1
            st.rerun()

# =======================================================
# MODO 3 — Simulado (com abas)
# =======================================================
elif modo == "Simulado":
    st.subheader("📝 Simulados")
    st.caption("Escolha um simulado abaixo. As questões são embaralhadas a cada início.")
    abas_nomes = ["Simulado 1", "Simulado 2", "Simulado 3", "Simulado 4", "Simulado Aleatório FK", "Personalizado", "Histórico"]
    tabs = st.tabs(abas_nomes)
    for tab, nome in zip(tabs, abas_nomes):
        with tab:
            if nome == "Simulado Aleatório FK":
                fontes = [bancos.get("Simulado 1", []), bancos.get("Simulado 2", []), bancos.get("Simulado 3", []), bancos.get("Simulado 4", [])]
                questoes_combinadas = []
                for f in fontes:
                    questoes_combinadas.extend(f)
                render_simulado(nome, questoes_combinadas, estado_key="aleatorio")
            elif nome == "Personalizado":
                fontes_personalizado = {nome: lista for nome, lista in bancos.items()}
                fonte_escolhida = st.selectbox("Fonte para o simulado personalizado", list(fontes_personalizado.keys()), key="fonte_personalizado")
                render_simulado("Personalizado", fontes_personalizado[fonte_escolhida], is_personalizado=True)
            elif nome == "Histórico":
                historico = db.carregar_simulados_historico()
                if not historico:
                    st.info("Nenhum simulado finalizado ainda.")
                else:
                    st.metric("Total de simulados", len(historico))
                    df_hist = pd.DataFrame(historico)
                    df_hist["data"] = pd.to_datetime(df_hist["data"])
                    df_hist["taxa"] = (df_hist["acertos"] / df_hist["total_questoes"] * 100).round(1)
                    st.dataframe(
                        df_hist[["data", "fonte", "total_questoes", "acertos", "nao_respondidas", "taxa"]]
                        .rename(columns={"data": "Data", "fonte": "Simulado", "total_questoes": "Total", "acertos": "Acertos", "nao_respondidas": "Não resp.", "taxa": "% Acertos"}),
                        use_container_width=True, hide_index=True,
                    )
                    if len(historico) > 1:
                        st.line_chart(df_hist.set_index("data")["taxa"])
                    for item in historico:
                        with st.expander(f"📅 {item['data']} - {item['fonte']} ({item['acertos']}/{item['total_questoes']})"):
                            detalhes = db.carregar_simulado_detalhes(item['id'])
                            if detalhes:
                                for det in detalhes:
                                    correto = (det['resposta'] == det['correta'])
                                    st.markdown(f"{'✅' if correto else '❌'} Q{det['questao_id']} — {det['codigo']} (Sua: {det['resposta']}, Correta: {det['correta']})")
                            else:
                                st.info("Detalhes não disponíveis.")
            else:
                fonte = bancos.get(nome, [])
                render_simulado(nome, fonte, estado_key=nome)

# =======================================================
# MODO 4 — Prova ANBIMA
# =======================================================
elif modo == "Prova":
    st.subheader("📝 Prova ANBIMA CGA")
    st.caption(f"{TOTAL_QUESTOES_PROVA} questões | 2h30 | Proporções oficiais")
    
    if not st.session_state.prova_ativo and not st.session_state.prova_finalizado:
        base_prova = bancos.get("Banco Principal", [])
        if not base_prova:
            st.warning("Banco Principal vazio. Não é possível gerar a prova.")
            st.stop()
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
            disponiveis = len([q for q in base_prova if q.get("tema") == tema_json])
            if disponiveis < qtd_necessaria:
                faltam = True
                st.error(f"❌ Tema '{tema_json}' tem apenas {disponiveis} questões, mas são necessárias {qtd_necessaria}.")
        if faltam:
            st.warning("Não há questões suficientes para montar a prova. Adicione mais questões ao banco principal.")
            st.stop()
        
        if st.button("🚀 Iniciar Prova", use_container_width=True):
            questoes_prova = []
            grupo_por_questao = {}
            for item in distribuicao:
                tema_json = item["tema_json"]
                qtd = item["quantidade"]
                grupo_nome = item["grupo_nome"]
                qs_tema = [q for q in base_prova if q.get("tema") == tema_json]
                amostra = random.sample(qs_tema, qtd)
                for q in amostra:
                    grupo_por_questao[q.get("id_unico", q["id"])] = grupo_nome
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
            # Salvar respostas pendentes
            for q_item in st.session_state.prova_questoes:
                registrar_resposta(q_item, st.session_state.prova_respostas.get(q_item.get("id_unico", q_item["id"])), "prova", salvar_imediato=False)
            persistir_tudo()
            # Salvar prova
            duracao = int(time.time() - st.session_state.inicio_prova)
            respostas_prova = []
            for q_item in st.session_state.prova_questoes:
                respostas_prova.append({
                    'questao_id': q_item.get("id_unico", q_item["id"]),
                    'tema': q_item.get('tema', ''),
                    'codigo': q_item['codigo'],
                    'modulo': st.session_state.prova_grupo_por_questao.get(q_item.get("id_unico", q_item["id"]), 'Outros'),
                    'resposta': st.session_state.prova_respostas.get(q_item.get("id_unico", q_item["id"])),
                    'correta': q_item['correta']
                })
            prova_data = {
                'data': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'duracao_segundos': duracao,
                'total_questoes': len(st.session_state.prova_questoes),
                'total_acertos': sum(1 for q in st.session_state.prova_questoes if st.session_state.prova_respostas.get(q.get("id_unico", q["id"])) == q["correta"])
            }
            db.salvar_prova(prova_data, respostas_prova)
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
            st.progress((i + 1) / len(prov), text=f"Questão {i+1} de {len(prov)} | {respondidas_n} respondidas")
        
        # Mapa de questões
        with st.expander("🗺️ Mapa de Questões", expanded=False):
            grupos = {}
            for idx, q_item in enumerate(prov):
                grupo = st.session_state.prova_grupo_por_questao.get(q_item.get("id_unico", q_item["id"]), 'Outros')
                if grupo not in grupos:
                    grupos[grupo] = []
                grupos[grupo].append((idx, q_item))
            for grupo, lista in grupos.items():
                st.markdown(f"**{grupo}**")
                for j in range(0, len(lista), 10):
                    cols = st.columns(10)
                    for k in range(10):
                        if j + k < len(lista):
                            idx, q_item = lista[j + k]
                            is_respondida = q_item.get("id_unico", q_item["id"]) in st.session_state.prova_respostas
                            is_atual = (idx == i)
                            label = str(idx+1)
                            if is_respondida:
                                color = "green"
                            else:
                                color = "red"
                            btn_style = f"background-color:{color}; color:white;" if is_respondida else f"background-color:#ffcccc; color:black;"
                            if is_atual:
                                btn_style += " border:3px solid yellow;"
                            cols[k].markdown(
                                f"""
                                <button style="{btn_style} padding:5px 10px; border-radius:5px; border:none; cursor:pointer;" 
                                        onclick="window.location.href='?prova_go={idx}'">
                                    {label}
                                </button>
                                """,
                                unsafe_allow_html=True
                            )
                    st.divider()
        
        st.divider()
        card_questao(q, mostrar_objetivo=False, mostrar_destaque=True)
        resposta_prova = render_alternativas_com_descarte(q, f"prova_{q.get('id_unico', q['id'])}_{i}")
        if resposta_prova is not None:
            st.session_state.prova_respostas[q.get("id_unico", q["id"])] = resposta_prova
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
                        st.rerun()
                    else:
                        st.session_state.prova_ativo = False
                        st.session_state.prova_finalizado = True
                        for q_item in prov:
                            registrar_resposta(q_item, st.session_state.prova_respostas.get(q_item.get("id_unico", q_item["id"])), "prova", salvar_imediato=False)
                        persistir_tudo()
                        duracao = int(time.time() - st.session_state.inicio_prova)
                        respostas_prova = []
                        for q_item in prov:
                            respostas_prova.append({
                                'questao_id': q_item.get("id_unico", q_item["id"]),
                                'tema': q_item.get('tema', ''),
                                'codigo': q_item['codigo'],
                                'modulo': st.session_state.prova_grupo_por_questao.get(q_item.get("id_unico", q_item["id"]), 'Outros'),
                                'resposta': st.session_state.prova_respostas.get(q_item.get("id_unico", q_item["id"])),
                                'correta': q_item['correta']
                            })
                        prova_data = {
                            'data': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'duracao_segundos': duracao,
                            'total_questoes': len(prov),
                            'total_acertos': sum(1 for q in prov if st.session_state.prova_respostas.get(q.get("id_unico", q["id"])) == q["correta"])
                        }
                        db.salvar_prova(prova_data, respostas_prova)
                        st.rerun()
            else:
                if st.button("⚠️ Confirmar mesmo assim", use_container_width=True):
                    st.session_state.prova_ativo = False
                    st.session_state.prova_finalizado = True
                    st.session_state.confirmar_finalizar = False
                    for q_item in prov:
                        registrar_resposta(q_item, st.session_state.prova_respostas.get(q_item.get("id_unico", q_item["id"])), "prova", salvar_imediato=False)
                    persistir_tudo()
                    duracao = int(time.time() - st.session_state.inicio_prova)
                    respostas_prova = []
                    for q_item in prov:
                        respostas_prova.append({
                            'questao_id': q_item.get("id_unico", q_item["id"]),
                            'tema': q_item.get('tema', ''),
                            'codigo': q_item['codigo'],
                            'modulo': st.session_state.prova_grupo_por_questao.get(q_item.get("id_unico", q_item["id"]), 'Outros'),
                            'resposta': st.session_state.prova_respostas.get(q_item.get("id_unico", q_item["id"])),
                            'correta': q_item['correta']
                        })
                    prova_data = {
                        'data': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'duracao_segundos': duracao,
                        'total_questoes': len(prov),
                        'total_acertos': sum(1 for q in prov if st.session_state.prova_respostas.get(q.get("id_unico", q["id"])) == q["correta"])
                    }
                    db.salvar_prova(prova_data, respostas_prova)
                    st.rerun()
        
        if st.session_state.confirmar_finalizar:
            st.warning(f"Você ainda tem **{nao_resp_n}** questão(ões) sem resposta. Confirme para encerrar ou navegue para respondê-las.")
    
    if st.session_state.prova_finalizado:
        prov = st.session_state.prova_questoes
        respostas = st.session_state.prova_respostas
        grupo_por_questao = st.session_state.prova_grupo_por_questao
        
        if not st.session_state.prova_registrado:
            st.session_state.prova_registrado = True
            persistir_tudo()
        
        acertos_prov = sum(1 for q_item in prov if respostas.get(q_item.get("id_unico", q_item["id"])) == q_item["correta"])
        total_prov = len(prov)
        nao_resp = sum(1 for q_item in prov if respostas.get(q_item.get("id_unico", q_item["id"])) is None)
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
            grupo = grupo_por_questao.get(q_item.get("id_unico", q_item["id"]), "Outros")
            if grupo not in grupos_ids:
                grupos_ids[grupo] = []
            grupos_ids[grupo].append(q_item.get("id_unico", q_item["id"]))
        
        ordem_grupos = [g["nome"] for g in GRUPOS_PROVA]
        if "Outros" in grupos_ids and "Outros" not in ordem_grupos:
            ordem_grupos.append("Outros")
        
        dados_tabela = []
        for grupo in ordem_grupos:
            if grupo not in grupos_ids:
                continue
            ids_questoes = grupos_ids[grupo]
            total = len(ids_questoes)
            corretas_por_id = {q.get("id_unico", q["id"]): q["correta"] for q in prov}
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
                num = q_item.get("numero_original", q_item.get("id_unico", q_item["id"]))
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
                    render_correcao(q_item, respostas.get(q_item.get("id_unico", q_item["id"])))
            
            with tabs[1]:
                lst = [q_item for q_item in prov if respostas.get(q_item.get("id_unico", q_item["id"])) == q_item["correta"]]
                if lst:
                    for q_item in lst:
                        render_correcao(q_item, respostas.get(q_item.get("id_unico", q_item["id"])))
                else:
                    st.info("Nenhum acerto.")
            
            with tabs[2]:
                lst = [
                    q_item for q_item in prov
                    if respostas.get(q_item.get("id_unico", q_item["id"])) is not None
                    and respostas.get(q_item.get("id_unico", q_item["id"])) != q_item["correta"]
                ]
                if lst:
                    for q_item in lst:
                        render_correcao(q_item, respostas.get(q_item.get("id_unico", q_item["id"])))
                else:
                    st.info("Nenhum erro.")
            
            with tabs[3]:
                lst = [q_item for q_item in prov if respostas.get(q_item.get("id_unico", q_item["id"])) is None]
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
    todas_questoes = []
    for lista in bancos.values():
        todas_questoes.extend(lista)
    mapa_questoes = {q.get("id_unico", q["id"]): q for q in todas_questoes}
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
# MODO 6 — Questões Destacadas
# =======================================================
elif modo == "Questões Destacadas":
    st.subheader("⭐ Revisão de Questões Destacadas")
    if not st.session_state.destacadas:
        st.info("Nenhuma questão destacada. Marque questões com o botão ⭐ durante os estudos.")
        st.stop()
    if not st.session_state.destacada_lista:
        todas = []
        for lista in bancos.values():
            todas.extend(lista)
        mapa = {q.get("id_unico", q["id"]): q for q in todas}
        questions = [mapa[qid] for qid in st.session_state.destacadas if qid in mapa]
        if not questions:
            st.info("As questões destacadas não foram encontradas nos bancos.")
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

    # Navegação
    col_prev, col_pos, col_info = st.columns([1, 1, 2])
    with col_prev:
        if st.button("◀ Anterior", disabled=(i == 0), use_container_width=True):
            st.session_state.destacada_i -= 1
            st.session_state.destacada_respondido = False
            st.session_state.destacada_resposta = None
            st.rerun()
    with col_pos:
        if st.button("Próxima ▶", disabled=(i >= total - 1), use_container_width=True):
            st.session_state.destacada_i += 1
            st.session_state.destacada_respondido = False
            st.session_state.destacada_resposta = None
            st.rerun()
    with col_info:
        st.caption(f"Questão {i + 1} de {total}")

    q = st.session_state.destacada_lista[i]
    st.divider()
    card_questao(q, mostrar_objetivo=True, mostrar_destaque=True)

    # --- RADIO COM DESCARTA (mesma lógica da revisão) ---
    qid = q.get("id_unico", q["id"])
    descartadas = st.session_state.alternativas_descartadas.get(qid, [])
    opcoes = list(q['opcoes'].keys())
    
    st.markdown("**Alternativas:**")
    opcoes_validas = [letra for letra in opcoes if letra not in descartadas]
    
    if descartadas:
        st.markdown("**Alternativas descartadas (clique em ↩️ para restaurar):**")
        for letra in descartadas:
            col1, col2 = st.columns([0.85, 0.15])
            with col1:
                st.markdown(f"~~{letra}) {q['opcoes'][letra]}~~")
            with col2:
                if st.button("↩️", key=f"restore_dest_{qid}_{letra}_{i}"):
                    descartadas.remove(letra)
                    st.session_state.alternativas_descartadas[qid] = descartadas
                    persistir_tudo()
                    st.rerun()
        st.divider()

    resposta_atual = st.session_state.destacada_resposta if st.session_state.destacada_respondido else None
    default_index = None
    if resposta_atual in opcoes_validas:
        default_index = opcoes_validas.index(resposta_atual)

    if opcoes_validas:
        selected = st.radio(
            "Escolha uma alternativa:",
            opcoes_validas,
            format_func=lambda x: f"{x}) {q['opcoes'][x]}",
            key=f"radio_dest_{qid}_{i}",
            index=default_index,
            disabled=st.session_state.destacada_respondido
        )
    else:
        selected = None
        st.warning("Todas as alternativas foram descartadas! Restaure alguma para responder.")

    if not st.session_state.destacada_respondido and selected is not None:
        st.session_state.destacada_resposta = selected

    if not st.session_state.destacada_respondido:
        if st.button("✅ Responder", use_container_width=True):
            if st.session_state.destacada_resposta is None:
                st.warning("Selecione uma alternativa antes de responder.")
            else:
                st.session_state.destacada_respondido = True
                registrar_resposta(q, st.session_state.destacada_resposta, "treino", salvar_imediato=True)
                st.rerun()
    else:
        mostrar_resultado(q, st.session_state.destacada_resposta)
        if st.button("⭐ Remover destaque", use_container_width=True):
            qid = q.get("id_unico", q["id"])
            if qid in st.session_state.destacadas:
                st.session_state.destacadas.remove(qid)
                db.remover_destacada(qid)
            st.session_state.destacada_lista = [item for item in st.session_state.destacada_lista if item.get("id_unico", item["id"]) != qid]
            if st.session_state.destacada_i >= len(st.session_state.destacada_lista):
                st.session_state.destacada_i = max(0, len(st.session_state.destacada_lista) - 1)
            st.session_state.destacada_respondido = False
            st.session_state.destacada_resposta = None
            st.rerun()

# =======================================================
# MODO 7 — Buscar Questão
# =======================================================
elif modo == "Buscar Questão":
    st.subheader("🔍 Buscar Questão por Código")
    codigo_busca = st.text_input("Digite o código da questão (ex: FK2979):", value=st.session_state.busca_codigo)
    if codigo_busca != st.session_state.busca_codigo:
        st.session_state.busca_codigo = codigo_busca
        st.session_state.busca_questao = None
        st.session_state.busca_respondido = False
        st.session_state.busca_resposta = None
    if st.button("🔎 Buscar", use_container_width=True) and codigo_busca:
        codigo_limpo = codigo_busca.strip().upper()
        import re
        codigo_sem_versao = re.sub(r'\s*[|]?\s*V\.\s*\d+$', '', codigo_limpo)
        encontrada = None
        for lista in bancos.values():
            for q in lista:
                codigo_q = re.sub(r'\s*[|]?\s*V\.\s*\d+$', '', q['codigo'].upper())
                if codigo_q == codigo_sem_versao:
                    encontrada = q
                    break
            if encontrada:
                break
        if encontrada:
            st.session_state.busca_questao = encontrada
            st.session_state.busca_respondido = False
            st.session_state.busca_resposta = None
        else:
            st.error(f"Questão com código '{codigo_busca}' não encontrada.")
            st.session_state.busca_questao = None
    if st.session_state.busca_questao:
        q = st.session_state.busca_questao
        st.divider()
        card_questao(q, mostrar_objetivo=True, mostrar_destaque=True)
        resposta = render_alternativas_com_descarte(q, f"busca_{q.get('id_unico', q['id'])}")
        if not st.session_state.busca_respondido:
            if st.button("✅ Responder", use_container_width=True):
                if resposta is None:
                    st.warning("Selecione uma alternativa antes de responder.")
                else:
                    st.session_state.busca_resposta = resposta
                    st.session_state.busca_respondido = True
                    registrar_resposta(q, resposta, "treino")
                    persistir_tudo()
                    st.rerun()
        else:
            mostrar_resultado(q, st.session_state.busca_resposta)
            if st.button("🔄 Nova busca", use_container_width=True):
                resetar_busca()
                st.rerun()

# =======================================================
# MODO 8 — Dashboard
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
        st.info("Ainda não há histórico. Responda questões no treino, revisão ou simulado para alimentar o painel.")
        st.stop()
    
    df = pd.DataFrame(st.session_state.historico)
    df["acertou_num"] = df["acertou"].astype(int)
    
    # GARANTE QUE A COLUNA "fonte" EXISTA
    if "fonte" not in df.columns:
        df["fonte"] = "Sem fonte"
    else:
        # Preenche valores nulos com "Sem fonte"
        df["fonte"] = df["fonte"].fillna("Sem fonte")
    
    st.divider()
    st.markdown("### Desempenho por modo de estudo")
    por_origem = df.groupby("origem").agg(total=("acertou_num", "count"), acertos=("acertou_num", "sum")).reset_index()
    por_origem["Taxa (%)"] = (por_origem["acertos"] / por_origem["total"] * 100).round(1)
    for _, row in por_origem.iterrows():
        label = LABEL_ORIGEM.get(row["origem"], row["origem"])
        st.progress(row["Taxa (%)"]/100, text=f"{label}: {row['Taxa (%)']:.1f}% ({row['acertos']}/{row['total']})")
    
    st.divider()
    st.markdown("### Desempenho por tema")
    tema_df = df.groupby("tema", dropna=False).agg(total=("acertou_num", "count"), acertos=("acertou_num", "sum")).reset_index()
    tema_df["tema"] = tema_df["tema"].fillna("Sem tema")
    tema_df["Taxa (%)"] = (tema_df["acertos"] / tema_df["total"] * 100).round(1)
    tema_df = tema_df.sort_values("Taxa (%)", ascending=False)
    st.bar_chart(tema_df.set_index("tema")["Taxa (%)"])
    with st.expander("📊 Tabela detalhada por tema"):
        st.dataframe(tema_df[["tema", "Taxa (%)", "acertos", "total"]].rename(columns={"tema":"Tema","acertos":"Acertos","total":"Total"}).style.format({"Taxa (%)":"{:.1f}"}), use_container_width=True)
    
    st.divider()
    st.markdown("### Desempenho por fonte")
    fonte_df = df.groupby("fonte", dropna=False).agg(total=("acertou_num", "count"), acertos=("acertou_num", "sum")).reset_index()
    fonte_df["fonte"] = fonte_df["fonte"].fillna("Sem fonte")
    fonte_df["Taxa (%)"] = (fonte_df["acertos"] / fonte_df["total"] * 100).round(1)
    fonte_df = fonte_df.sort_values("Taxa (%)", ascending=False)
    st.bar_chart(fonte_df.set_index("fonte")["Taxa (%)"])
    with st.expander("📊 Tabela detalhada por fonte"):
        st.dataframe(fonte_df[["fonte", "Taxa (%)", "acertos", "total"]].rename(columns={"fonte":"Fonte","acertos":"Acertos","total":"Total"}).style.format({"Taxa (%)":"{:.1f}"}), use_container_width=True)
    
    st.divider()
    st.markdown("### Desempenho por objetivo")
    obj_df = df.groupby("objetivo", dropna=False).agg(total=("acertou_num", "count"), acertos=("acertou_num", "sum")).reset_index()
    obj_df["objetivo"] = obj_df["objetivo"].fillna("Sem objetivo")
    obj_df["Taxa (%)"] = (obj_df["acertos"] / obj_df["total"] * 100).round(1)
    obj_df = obj_df.sort_values("Taxa (%)", ascending=False)
    obj_df["Objetivo curto"] = obj_df["objetivo"].apply(lambda x: (x[:57]+"...") if len(x)>60 else x)
    st.bar_chart(obj_df.set_index("Objetivo curto")["Taxa (%)"])
    with st.expander("📊 Tabela detalhada por objetivo"):
        st.dataframe(obj_df[["objetivo", "Taxa (%)", "acertos", "total"]].rename(columns={"objetivo":"Objetivo","acertos":"Acertos","total":"Total"}).style.format({"Taxa (%)":"{:.1f}"}), use_container_width=True)
    
    st.divider()
    if len(st.session_state.historico) >= 5:
        st.markdown("### Evolução da taxa de acerto — média móvel (janela 10)")
        df["media_movel"] = df["acertou_num"].rolling(window=10, min_periods=1).mean().mul(100).round(1)
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
        fonte_label = h.get("fonte", "Sem fonte")
        st.write(f"{icon} **{tema_label}** | Q{num} — {h['codigo']} {f'({fonte_label})' if fonte_label else ''} | Marcada: **{resp}** | Correta: **{h['correta']}** | _{origem_label}_")
