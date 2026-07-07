import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any

DB_PATH = "cga_data.db"

def init_db():
    """Cria todas as tabelas necessárias."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Histórico
    c.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            id_questao INTEGER,
            numero_original INTEGER,
            tema TEXT,
            codigo TEXT,
            objetivo TEXT,
            resposta TEXT,
            correta TEXT,
            acertou INTEGER,
            origem TEXT
        )
    ''')
    
    # Estado geral
    c.execute('''
        CREATE TABLE IF NOT EXISTS estado (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    ''')
    
    # Leitner (nível e próxima revisão por questão)
    c.execute('''
        CREATE TABLE IF NOT EXISTS leitner (
            questao_id INTEGER PRIMARY KEY,
            nivel INTEGER,
            proxima TEXT
        )
    ''')
    
    # Descartar alternativas (armazena lista de letras descartadas por questão)
    c.execute('''
        CREATE TABLE IF NOT EXISTS descartes (
            questao_id INTEGER PRIMARY KEY,
            letras TEXT   -- JSON array, ex: '["A", "C"]'
        )
    ''')
    
    conn.commit()
    conn.close()

# -------------------------------------------------------
# Histórico
# -------------------------------------------------------
def save_historico(historico: List[Dict[str, Any]]):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM historico")
    for reg in historico:
        c.execute('''
            INSERT INTO historico (
                data, id_questao, numero_original, tema, codigo, objetivo,
                resposta, correta, acertou, origem
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            reg.get('data'),
            reg.get('id'),
            reg.get('numero_original'),
            reg.get('tema'),
            reg.get('codigo'),
            reg.get('objetivo'),
            reg.get('resposta'),
            reg.get('correta'),
            1 if reg.get('acertou') else 0,
            reg.get('origem')
        ))
    conn.commit()
    conn.close()

def load_historico() -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT data, id_questao, numero_original, tema, codigo, objetivo,
               resposta, correta, acertou, origem
        FROM historico
        ORDER BY id ASC
    ''')
    rows = c.fetchall()
    conn.close()
    historico = []
    for row in rows:
        historico.append({
            'data': row[0],
            'id': row[1],
            'numero_original': row[2],
            'tema': row[3],
            'codigo': row[4],
            'objetivo': row[5],
            'resposta': row[6],
            'correta': row[7],
            'acertou': bool(row[8]),
            'origem': row[9]
        })
    return historico

# -------------------------------------------------------
# Estado geral
# -------------------------------------------------------
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
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    json_str = json.dumps(estado_filtrado, default=str)
    c.execute("REPLACE INTO estado (chave, valor) VALUES (?, ?)", ('state', json_str))
    conn.commit()
    conn.close()

def load_estado() -> Dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT valor FROM estado WHERE chave = ?", ('state',))
    row = c.fetchone()
    conn.close()
    if row is None:
        return {}
    try:
        return json.loads(row[0])
    except:
        return {}

# -------------------------------------------------------
# Erros (reconstrução a partir dos IDs)
# -------------------------------------------------------
def load_erros(questoes: List[Dict]) -> List[Dict]:
    estado = load_estado()
    erros_ids = estado.get('erros_ids', [])
    mapa = {q['id']: q for q in questoes}
    return [mapa[eid] for eid in erros_ids if eid in mapa]

# -------------------------------------------------------
# Leitner
# -------------------------------------------------------
def save_leitner(questao_id: int, nivel: int, proxima: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        REPLACE INTO leitner (questao_id, nivel, proxima)
        VALUES (?, ?, ?)
    ''', (questao_id, nivel, proxima))
    conn.commit()
    conn.close()

def load_leitner() -> Dict[int, Dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT questao_id, nivel, proxima FROM leitner")
    rows = c.fetchall()
    conn.close()
    result = {}
    for qid, nivel, proxima in rows:
        result[qid] = {'nivel': nivel, 'proxima': proxima}
    return result

# -------------------------------------------------------
# Descartar alternativas
# -------------------------------------------------------
def save_descartes(questao_id: int, letras: List[str]):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    json_letras = json.dumps(letras)
    c.execute('''
        REPLACE INTO descartes (questao_id, letras)
        VALUES (?, ?)
    ''', (questao_id, json_letras))
    conn.commit()
    conn.close()

def load_descartes() -> Dict[int, List[str]]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT questao_id, letras FROM descartes")
    rows = c.fetchall()
    conn.close()
    result = {}
    for qid, letras_json in rows:
        try:
            result[qid] = json.loads(letras_json)
        except:
            result[qid] = []
    return result
