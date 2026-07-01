# Simulador CGA — Avaliação de Desempenho

App web em Streamlit para estudar questões de CGA com:

- Treino livre com feedback imediato
- Revisão automática de erros
- Simulado com timer
- Dashboard de desempenho
- Filtro por objetivo da questão

## Como rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Como publicar para usar no celular

1. Crie um repositório no GitHub.
2. Suba estes arquivos:
   - `app.py`
   - `questoes_cga_avaliacao_desempenho_final.json`
   - `requirements.txt`
3. Acesse Streamlit Cloud.
4. Clique em `New app`.
5. Selecione o repositório e o arquivo `app.py`.
6. Faça deploy.
7. Abra o link no celular e adicione à tela inicial.

## Observação

O histórico fica salvo enquanto a sessão do navegador estiver ativa. Para salvar histórico permanente entre sessões, o próximo passo é adicionar armazenamento em arquivo, Google Sheets, Supabase ou SQLite.
