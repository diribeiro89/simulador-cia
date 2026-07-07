# database.py
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any

DB_PATH = "cga_data.db"

def init_db():
    """Cria as tabelas se não existirem."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Tabela de histórico
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
    # Tabela de estado (apenas uma linha, chave 'state')
    c.execute('''
        CREATE TABLE IF NOT EXISTS estado (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_historico(historico: List[Dict[str, Any]]):
    """Substitui todo o histórico pelo novo."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Limpa tabela
    c.execute("DELETE FROM historico")
    # Insere todos os registros
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
    """Retorna lista de dicionários com o histórico."""
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

def save_estado(estado: Dict[str, Any]):
    """Salva o estado atual (modo, filtros, índices, etc.) como JSON."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Serializa apenas as chaves que queremos persistir
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
    # Para objetos não serializáveis, convertemos
    # Exemplo: simulado_questoes é lista de dicts, simulado_respostas é dict
    # Também precisamos salvar erros e acertos (listas de IDs)
    estado_filtrado['erros_ids'] = [e['id'] for e in estado.get('erros', [])]
    estado_filtrado['acertos_ids'] = estado.get('acertos', [])
    # Converte para JSON
    json_str = json.dumps(estado_filtrado, default=str)
    c.execute("REPLACE INTO estado (chave, valor) VALUES (?, ?)", ('state', json_str))
    conn.commit()
    conn.close()

def load_estado() -> Dict[str, Any]:
    """Carrega o estado salvo, retorna dicionário vazio se não existir."""
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

def save_erros(erros: List[Dict]):
    """Salva a lista de erros (dicionários completos) como JSON separado? 
       Podemos salvar apenas IDs e reconstruir a partir do JSON de questões.
       Mas para simplificar, salvamos os IDs e depois carregamos os objetos completos.
       Vamos fazer isso dentro de save_estado (já incluímos erros_ids).
       Então não precisamos de função separada.
    """
    pass  # já incluso no save_estado

def load_erros(questoes: List[Dict]) -> List[Dict]:
    """Reconstrói a lista de erros a partir dos IDs salvos e do banco de questões."""
    estado = load_estado()
    erros_ids = estado.get('erros_ids', [])
    # Mapeia id -> questão
    mapa = {q['id']: q for q in questoes}
    erros = [mapa[eid] for eid in erros_ids if eid in mapa]
    return erros