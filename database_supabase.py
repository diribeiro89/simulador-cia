import streamlit as st
import json
from datetime import datetime
from typing import List, Dict, Any
from supabase import create_client, Client

# ========================================
# CONFIGURAÇÃO VIA SECRETS (Streamlit Cloud)
# ========================================
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]

# Inicializa o cliente Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def init_db():
    """As tabelas já são criadas via SQL no Supabase."""
    pass

# ========================================
# HISTÓRICO
# ========================================
def save_historico(historico: List[Dict[str, Any]]):
    supabase.table("historico").delete().neq("id", 0).execute()
    for reg in historico:
        supabase.table("historico").insert({
            "data": reg.get('data'),
            "id_questao": reg.get('id'),
            "numero_original": reg.get('numero_original'),
            "tema": reg.get('tema'),
            "codigo": reg.get('codigo'),
            "objetivo": reg.get('objetivo'),
            "resposta": reg.get('resposta'),
            "correta": reg.get('correta'),
            "acertou": 1 if reg.get('acertou') else 0,
            "origem": reg.get('origem')
        }).execute()

def load_historico() -> List[Dict[str, Any]]:
    response = supabase.table("historico").select("*").order("id", desc=False).execute()
    historico = []
    for row in response.data:
        historico.append({
            'data': row['data'],
            'id': row['id_questao'],
            'numero_original': row['numero_original'],
            'tema': row['tema'],
            'codigo': row['codigo'],
            'objetivo': row['objetivo'],
            'resposta': row['resposta'],
            'correta': row['correta'],
            'acertou': bool(row['acertou']),
            'origem': row['origem']
        })
    return historico

# ========================================
# ESTADO
# ========================================
def save_estado(estado: Dict[str, Any]):
    chaves_persistir = [
        'modo', 'filtro_tema_atual', 'filtro_objetivo_atual',
        'questao_atual', 'respondido', 'resposta_usuario',
        'simulado_questoes', 'simulado_respostas', 'simulado_i',
        'simulado_ativo', 'simulado_finalizado', 'simulado_registrado',
        'inicio_simulado', 'duracao_simulado_min',
        'revisao_lista', 'revisao_i', 'revisao_concluida',
        'confirmar_finalizar'
    ]
    estado_filtrado = {k: estado.get(k) for k in chaves_persistir if k in estado}
    estado_filtrado['erros_ids'] = [e['id'] for e in estado.get('erros', [])]
    estado_filtrado['acertos_ids'] = estado.get('acertos', [])
    
    json_str = json.dumps(estado_filtrado, default=str)
    supabase.table("estado").upsert({
        "chave": "state",
        "valor": json_str
    }).execute()

def load_estado() -> Dict[str, Any]:
    response = supabase.table("estado").select("*").eq("chave", "state").execute()
    if not response.data:
        return {}
    try:
        return json.loads(response.data[0]['valor'])
    except:
        return {}

# ========================================
# ERROS
# ========================================
def load_erros(questoes: List[Dict]) -> List[Dict]:
    estado = load_estado()
    erros_ids = estado.get('erros_ids', [])
    mapa = {q['id']: q for q in questoes}
    return [mapa[eid] for eid in erros_ids if eid in mapa]

# ========================================
# LEITNER
# ========================================
def save_leitner(questao_id: int, nivel: int, proxima: str):
    supabase.table("leitner").upsert({
        "questao_id": questao_id,
        "nivel": nivel,
        "proxima": proxima
    }).execute()

def load_leitner() -> Dict[int, Dict]:
    response = supabase.table("leitner").select("*").execute()
    result = {}
    for row in response.data:
        result[row['questao_id']] = {'nivel': row['nivel'], 'proxima': row['proxima']}
    return result

# ========================================
# DESCARTES
# ========================================
def save_descartes(questao_id: int, letras: List[str]):
    json_letras = json.dumps(letras)
    supabase.table("descartes").upsert({
        "questao_id": questao_id,
        "letras": json_letras
    }).execute()

def load_descartes() -> Dict[int, List[str]]:
    response = supabase.table("descartes").select("*").execute()
    result = {}
    for row in response.data:
        try:
            result[row['questao_id']] = json.loads(row['letras'])
        except:
            result[row['questao_id']] = []
    return result

# ========================================
# PROVAS
# ========================================
def salvar_prova(prova_data, respostas):
    response = supabase.table("provas").insert({
        "data": prova_data['data'],
        "duracao_segundos": prova_data['duracao_segundos'],
        "total_questoes": prova_data['total_questoes'],
        "total_acertos": prova_data['total_acertos']
    }).execute()
    prova_id = response.data[0]['id']
    
    for resp in respostas:
        supabase.table("respostas_prova").insert({
            "prova_id": prova_id,
            "questao_id": resp['questao_id'],
            "tema": resp['tema'],
            "codigo": resp['codigo'],
            "modulo": resp['modulo'],
            "resposta": resp['resposta'],
            "correta": resp['correta']
        }).execute()
    return prova_id

def carregar_provas():
    response = supabase.table("provas").select("*").order("id", desc=True).execute()
    provas = []
    for row in response.data:
        provas.append({
            'id': row['id'],
            'data': row['data'],
            'duracao_segundos': row['duracao_segundos'],
            'total_questoes': row['total_questoes'],
            'total_acertos': row['total_acertos']
        })
    return provas

def carregar_respostas_prova(prova_id):
    response = supabase.table("respostas_prova").select("*").eq("prova_id", prova_id).execute()
    respostas = []
    for row in response.data:
        respostas.append({
            'questao_id': row['questao_id'],
            'tema': row['tema'],
            'codigo': row['codigo'],
            'modulo': row['modulo'],
            'resposta': row['resposta'],
            'correta': row['correta']
        })
    return respostas

def limpar_provas():
    supabase.table("respostas_prova").delete().neq("id", 0).execute()
    supabase.table("provas").delete().neq("id", 0).execute()

# ========================================
# DESTACADAS
# ========================================
def adicionar_destacada(questao_id):
    supabase.table("destacadas").upsert({
        "questao_id": questao_id,
        "data_destaque": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }).execute()

def remover_destacada(questao_id):
    supabase.table("destacadas").delete().eq("questao_id", questao_id).execute()

def carregar_destacadas():
    response = supabase.table("destacadas").select("*").execute()
    return {row['questao_id'] for row in response.data}

def limpar_destacadas():
    supabase.table("destacadas").delete().neq("questao_id", 0).execute()

# ========================================
# HISTÓRICO DE SIMULADOS
# ========================================
def salvar_simulado_historico(historico_data):
    """
    historico_data = {
        'data': str,
        'fonte': str,
        'total_questoes': int,
        'acertos': int,
        'nao_respondidas': int,
        'tempo_segundos': int,
        'questoes_ids': list (opcional)
    }
    """
    supabase.table("simulados_historico").insert({
        "data": historico_data['data'],
        "fonte": historico_data['fonte'],
        "total_questoes": historico_data['total_questoes'],
        "acertos": historico_data['acertos'],
        "nao_respondidas": historico_data['nao_respondidas'],
        "tempo_segundos": historico_data['tempo_segundos'],
        "questoes_ids": json.dumps(historico_data.get('questoes_ids', []))
    }).execute()

def carregar_simulados_historico():
    response = supabase.table("simulados_historico").select("*").order("id", desc=True).execute()
    historico = []
    for row in response.data:
        historico.append({
            'id': row['id'],
            'data': row['data'],
            'fonte': row['fonte'],
            'total_questoes': row['total_questoes'],
            'acertos': row['acertos'],
            'nao_respondidas': row['nao_respondidas'],
            'tempo_segundos': row['tempo_segundos'],
            'questoes_ids': json.loads(row['questoes_ids']) if row['questoes_ids'] else []
        })
    return historico

def limpar_simulados_historico():
    supabase.table("simulados_historico").delete().neq("id", 0).execute()

# ========================================
# ESTATÍSTICAS POR QUESTÃO
# ========================================
def atualizar_estatistica_questao(questao_id, acertou):
    """Incrementa acertos ou erros para uma questão."""
    # Busca registro existente
    response = supabase.table("estatisticas_questoes").select("*").eq("questao_id", questao_id).execute()
    if response.data:
        registro = response.data[0]
        novos_dados = {
            "acertos": registro["acertos"] + (1 if acertou else 0),
            "erros": registro["erros"] + (0 if acertou else 1),
            "total": registro["total"] + 1
        }
        supabase.table("estatisticas_questoes").update(novos_dados).eq("questao_id", questao_id).execute()
    else:
        supabase.table("estatisticas_questoes").insert({
            "questao_id": questao_id,
            "acertos": 1 if acertou else 0,
            "erros": 0 if acertou else 1,
            "total": 1
        }).execute()

def carregar_estatisticas_questoes():
    response = supabase.table("estatisticas_questoes").select("*").execute()
    dados = {}
    for row in response.data:
        dados[row["questao_id"]] = {"acertos": row["acertos"], "erros": row["erros"], "total": row["total"]}
    return dados

# ========================================
# HISTÓRICO DE SIMULADOS (detalhado)
# ========================================
def salvar_simulado_historico(historico_data, respostas_detalhadas):
    """
    historico_data: dict com data, fonte, total_questoes, acertos, nao_respondidas, tempo_segundos
    respostas_detalhadas: lista de dict com questao_id, resposta, correta, tema, codigo, fonte
    """
    # Insere o cabeçalho
    response = supabase.table("simulados_historico").insert({
        "data": historico_data['data'],
        "fonte": historico_data['fonte'],
        "total_questoes": historico_data['total_questoes'],
        "acertos": historico_data['acertos'],
        "nao_respondidas": historico_data['nao_respondidas'],
        "tempo_segundos": historico_data['tempo_segundos'],
        "questoes_ids": json.dumps([r['questao_id'] for r in respostas_detalhadas])
    }).execute()
    sim_id = response.data[0]['id']
    
    # Insere as respostas detalhadas em uma tabela separada
    for resp in respostas_detalhadas:
        supabase.table("simulados_detalhes").insert({
            "simulado_id": sim_id,
            "questao_id": resp['questao_id'],
            "resposta": resp['resposta'],
            "correta": resp['correta'],
            "tema": resp['tema'],
            "codigo": resp['codigo'],
            "fonte": resp['fonte']
        }).execute()

def carregar_simulados_historico():
    response = supabase.table("simulados_historico").select("*").order("id", desc=True).execute()
    historico = []
    for row in response.data:
        historico.append({
            'id': row['id'],
            'data': row['data'],
            'fonte': row['fonte'],
            'total_questoes': row['total_questoes'],
            'acertos': row['acertos'],
            'nao_respondidas': row['nao_respondidas'],
            'tempo_segundos': row['tempo_segundos'],
            'questoes_ids': json.loads(row['questoes_ids']) if row['questoes_ids'] else []
        })
    return historico

def carregar_simulado_detalhes(simulado_id):
    response = supabase.table("simulados_detalhes").select("*").eq("simulado_id", simulado_id).execute()
    detalhes = []
    for row in response.data:
        detalhes.append({
            'questao_id': row['questao_id'],
            'resposta': row['resposta'],
            'correta': row['correta'],
            'tema': row['tema'],
            'codigo': row['codigo'],
            'fonte': row['fonte']
        })
    return detalhes

def limpar_simulados_historico():
    supabase.table("simulados_detalhes").delete().neq("id", 0).execute()
    supabase.table("simulados_historico").delete().neq("id", 0).execute()
