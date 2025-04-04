import sqlite3
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import time

# =============================================
# CONFIGURAÇÃO PARA RODAR 24/7
# =============================================



def backup_db():
    """Função de backup"""
    if os.path.exists('vendas.db'):
        try:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            os.rename('vendas.db', backup_name)
            st.success(f"Backup criado: {backup_name}")
        except Exception as e:
            st.error(f"Erro no backup: {e}")

# =============================================
# CONFIGURAÇÃO DO BANCO DE DADOS
# =============================================
def criar_banco():
    conn = sqlite3.connect('vendas.db', check_same_thread=False)
    cursor = conn.cursor()

    # Tabela Clientes
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        celular TEXT NOT NULL,
        email TEXT,
        endereco TEXT,
        data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP,
        ativo INTEGER DEFAULT 1
    )''')

    # Tabela Produtos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        descricao TEXT,
        preco_venda REAL NOT NULL,
        custo_producao REAL DEFAULT 0,
        estoque INTEGER NOT NULL,
        data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP,
        ativo INTEGER DEFAULT 1
    )''')

    # Tabela Vendas
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vendas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER NOT NULL,
        data_venda TEXT DEFAULT CURRENT_TIMESTAMP,
        valor_total REAL NOT NULL,
        lucro_total REAL DEFAULT 0,
        status TEXT DEFAULT 'finalizada',
        FOREIGN KEY (cliente_id) REFERENCES clientes (id)
    )''')

    # Tabela Itens Venda
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS itens_venda (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        venda_id INTEGER NOT NULL,
        produto_id INTEGER NOT NULL,
        quantidade INTEGER NOT NULL,
        preco_unitario REAL NOT NULL,
        custo_unitario REAL NOT NULL,
        FOREIGN KEY (venda_id) REFERENCES vendas (id),
        FOREIGN KEY (produto_id) REFERENCES produtos (id)
    )''')

    conn.commit()
    return conn

# =============================================
# MÓDULO DE CLIENTES
# =============================================
def modulo_clientes(conn):
    st.title("📋 Gestão de Clientes")

    tab1, tab2 = st.tabs(["Cadastrar", "Listar/Editar"])

    with tab1:
        st.subheader("Novo Cliente")
        with st.form("form_cliente"):
            nome = st.text_input("Nome Completo*")
            celular = st.text_input("Celular*")
            email = st.text_input("Email")
            endereco = st.text_area("Endereço")

            if st.form_submit_button("Salvar"):
                if nome and celular:
                    cursor = conn.cursor()
                    cursor.execute(
                        """INSERT INTO clientes 
                        (nome, celular, email, endereco) 
                        VALUES (?, ?, ?, ?)""",
                        (nome, celular, email, endereco)
                    )
                    conn.commit()
                    st.success("Cliente cadastrado com sucesso!")
                else:
                    st.error("Campos obrigatórios (*) não preenchidos!")

    with tab2:
        st.subheader("Clientes Cadastrados")
        df = pd.read_sql("SELECT * FROM clientes WHERE ativo = 1", conn)

        # Edição de clientes
        with st.expander("Editar Cliente"):
            clientes = pd.read_sql("SELECT id, nome FROM clientes WHERE ativo = 1", conn)
            cliente_selecionado = st.selectbox(
                "Selecione o cliente",
                clientes['id'],
                format_func=lambda x: f"{x} - {clientes[clientes['id'] == x]['nome'].values[0]}"
            )

            if cliente_selecionado:
                dados_cliente = pd.read_sql(
                    f"SELECT * FROM clientes WHERE id = {cliente_selecionado}", 
                    conn
                ).iloc[0]

                with st.form("form_editar_cliente"):
                    novo_nome = st.text_input("Nome", value=dados_cliente['nome'])
                    novo_celular = st.text_input("Celular", value=dados_cliente['celular'])
                    novo_email = st.text_input("Email", value=dados_cliente['email'])
                    novo_endereco = st.text_area("Endereço", value=dados_cliente['endereco'])

                    if st.form_submit_button("Atualizar"):
                        cursor = conn.cursor()
                        cursor.execute(
                            """UPDATE clientes SET
                            nome = ?, celular = ?, email = ?, endereco = ?
                            WHERE id = ?""",
                            (novo_nome, novo_celular, novo_email, novo_endereco, cliente_selecionado)
                        )
                        conn.commit()
                        st.success("Cliente atualizado!")

        st.dataframe(df, use_container_width=True)

# =============================================
# MÓDULO DE PRODUTOS
# =============================================
def modulo_produtos(conn):
    st.title("📦 Gestão de Produtos")

    tab1, tab2 = st.tabs(["Cadastrar", "Listar/Editar"])

    with tab1:
        st.subheader("Novo Produto")
        with st.form("form_produto"):
            nome = st.text_input("Nome do Produto*")
            descricao = st.text_area("Descrição")
            preco = st.number_input("Preço de Venda*", min_value=0.0, step=0.01)
            custo = st.number_input("Custo de Produção", min_value=0.0, step=0.01, value=0.0)
            estoque = st.number_input("Estoque Inicial*", min_value=0, step=1)

            if st.form_submit_button("Salvar"):
                if nome and preco and estoque >= 0:
                    cursor = conn.cursor()
                    cursor.execute(
                        """INSERT INTO produtos 
                        (nome, descricao, preco_venda, custo_producao, estoque) 
                        VALUES (?, ?, ?, ?, ?)""",
                        (nome, descricao, preco, custo, estoque)
                    )
                    conn.commit()
                    st.success("Produto cadastrado com sucesso!")
                else:
                    st.error("Preencha os campos obrigatórios (*)")

    with tab2:
        st.subheader("Produtos Cadastrados")
        df = pd.read_sql("SELECT * FROM produtos WHERE ativo = 1", conn)

        with st.expander("Editar Produto"):
            produtos = pd.read_sql("SELECT id, nome FROM produtos WHERE ativo = 1", conn)
            produto_selecionado = st.selectbox(
                "Selecione o produto",
                produtos['id'],
                format_func=lambda x: f"{x} - {produtos[produtos['id'] == x]['nome'].values[0]}"
            )

            if produto_selecionado:
                dados_produto = pd.read_sql(
                    f"SELECT * FROM produtos WHERE id = {produto_selecionado}", 
                    conn
                ).iloc[0]

                with st.form("form_editar_produto"):
                    novo_nome = st.text_input("Nome", value=dados_produto['nome'])
                    nova_descricao = st.text_area("Descrição", value=dados_produto['descricao'])
                    novo_preco = st.number_input(
                        "Preço", 
                        min_value=0.0, 
                        step=0.01, 
                        value=float(dados_produto['preco_venda'])
                    )
                    novo_custo = st.number_input(
                        "Custo", 
                        min_value=0.0, 
                        step=0.01, 
                        value=float(dados_produto['custo_producao'])
                    )
                    novo_estoque = st.number_input(
                        "Estoque", 
                        min_value=0, 
                        step=1, 
                        value=int(dados_produto['estoque'])
                    )

                    if st.form_submit_button("Atualizar"):
                        cursor = conn.cursor()
                        cursor.execute(
                            """UPDATE produtos SET
                            nome = ?, descricao = ?, preco_venda = ?, 
                            custo_producao = ?, estoque = ?
                            WHERE id = ?""",
                            (novo_nome, nova_descricao, novo_preco, novo_custo, novo_estoque, produto_selecionado)
                        )
                        conn.commit()
                        st.success("Produto atualizado!")

        st.dataframe(df, use_container_width=True)

# =============================================
# MÓDULO DE VENDAS
# =============================================
def modulo_vendas(conn):
    st.title("💰 Gestão de Vendas")

    tab1, tab2 = st.tabs(["Nova Venda", "Histórico"])

    with tab1:
        st.subheader("Registrar Nova Venda")

        # Selecionar cliente
        clientes = pd.read_sql("SELECT id, nome FROM clientes WHERE ativo = 1", conn)
        cliente_id = st.selectbox(
            "Cliente*",
            clientes['id'],
            format_func=lambda x: f"{x} - {clientes[clientes['id'] == x]['nome'].values[0]}"
        )

        # Adicionar produtos
        produtos = pd.read_sql("SELECT id, nome, preco_venda, custo_producao, estoque FROM produtos WHERE ativo = 1 AND estoque > 0", conn)

        if produtos.empty:
            st.warning("Nenhum produto disponível em estoque!")
            return

        itens_venda = []
        col1, col2, col3 = st.columns(3)

        with col1:
            produto_id = st.selectbox(
                "Produto",
                produtos['id'],
                format_func=lambda x: f"{x} - {produtos[produtos['id'] == x]['nome'].values[0]}"
            )
        with col2:
            quantidade = st.number_input("Quantidade", min_value=1, step=1, value=1)
        with col3:
            if st.button("Adicionar"):
                produto = produtos[produtos['id'] == produto_id].iloc[0]
                if quantidade > produto['estoque']:
                    st.error("Quantidade indisponível em estoque!")
                else:
                    itens_venda.append({
                        'produto_id': produto_id,
                        'nome': produto['nome'],
                        'quantidade': quantidade,
                        'preco_unitario': produto['preco_venda'],
                        'custo_unitario': produto['custo_producao'],
                        'subtotal': quantidade * produto['preco_venda']
                    })
                    st.success("Produto adicionado!")

        # Lista de itens adicionados
        if itens_venda:
            st.subheader("Itens da Venda")
            df_itens = pd.DataFrame(itens_venda)
            st.dataframe(df_itens)

            total_venda = df_itens['subtotal'].sum()
            st.metric("Total da Venda", f"R$ {total_venda:.2f}")

            if st.button("Finalizar Venda"):
                try:
                    cursor = conn.cursor()

                    # Calcula lucro total
                    lucro_total = sum(
                        (item['preco_unitario'] - item['custo_unitario']) * item['quantidade']
                        for item in itens_venda
                    )

                    # Insere venda
                    cursor.execute(
                        """INSERT INTO vendas 
                        (cliente_id, valor_total, lucro_total) 
                        VALUES (?, ?, ?)""",
                        (cliente_id, total_venda, lucro_total)
                    )
                    venda_id = cursor.lastrowid

                    # Insere itens da venda
                    for item in itens_venda:
                        cursor.execute(
                            """INSERT INTO itens_venda 
                            (venda_id, produto_id, quantidade, preco_unitario, custo_unitario) 
                            VALUES (?, ?, ?, ?, ?)""",
                            (venda_id, item['produto_id'], item['quantidade'], 
                             item['preco_unitario'], item['custo_unitario'])
                        )

                        # Atualiza estoque
                        cursor.execute(
                            "UPDATE produtos SET estoque = estoque - ? WHERE id = ?",
                            (item['quantidade'], item['produto_id'])
                        )

                    conn.commit()
                    st.success("Venda registrada com sucesso!")
                    st.balloons()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Erro ao registrar venda: {e}")

    with tab2:
        st.subheader("Histórico de Vendas")
        vendas = pd.read_sql("""
            SELECT v.id, c.nome as cliente, v.data_venda, v.valor_total, v.lucro_total 
            FROM vendas v
            JOIN clientes c ON v.cliente_id = c.id
            ORDER BY v.data_venda DESC
        """, conn)

        st.dataframe(vendas, use_container_width=True)

        # Detalhes da venda selecionada
        if not vendas.empty:
            venda_selecionada = st.selectbox(
                "Selecione uma venda para detalhar",
                vendas['id'],
                format_func=lambda x: f"Venda {x} - {vendas[vendas['id'] == x]['cliente'].values[0]} - R$ {vendas[vendas['id'] == x]['valor_total'].values[0]:.2f}"
            )

            if venda_selecionada:
                detalhes_venda = pd.read_sql(f"""
                    SELECT p.nome as produto, iv.quantidade, iv.preco_unitario, 
                           (iv.quantidade * iv.preco_unitario) as subtotal
                    FROM itens_venda iv
                    JOIN produtos p ON iv.produto_id = p.id
                    WHERE iv.venda_id = {venda_selecionada}
                """, conn)

                st.dataframe(detalhes_venda)

# =============================================
# MÓDULO DE RELATÓRIOS
# =============================================
def modulo_relatorios(conn):
    st.title("📊 Relatórios")

    tab1, tab2, tab3 = st.tabs(["Vendas", "Produtos", "Clientes"])

    with tab1:
        st.subheader("Relatório de Vendas")

        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input("Data Início")
        with col2:
            data_fim = st.date_input("Data Fim")

        if st.button("Gerar Relatório"):
            vendas = pd.read_sql(f"""
                SELECT v.id, c.nome as cliente, v.data_venda, v.valor_total, v.lucro_total
                FROM vendas v
                JOIN clientes c ON v.cliente_id = c.id
                WHERE date(v.data_venda) BETWEEN '{data_inicio}' AND '{data_fim}'
                ORDER BY v.data_venda
            """, conn)

            if not vendas.empty:
                st.dataframe(vendas)

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total de Vendas", f"R$ {vendas['valor_total'].sum():.2f}")
                with col2:
                    st.metric("Lucro Total", f"R$ {vendas['lucro_total'].sum():.2f}")

                st.bar_chart(vendas.set_index('data_venda')['valor_total'])
            else:
                st.warning("Nenhuma venda no período selecionado")

    with tab2:
        st.subheader("Relatório de Produtos")
        produtos = pd.read_sql("""
            SELECT p.nome, p.estoque, 
                   SUM(CASE WHEN iv.id IS NOT NULL THEN iv.quantidade ELSE 0 END) as vendidos,
                   p.preco_venda, p.custo_producao
            FROM produtos p
            LEFT JOIN itens_venda iv ON p.id = iv.produto_id
            GROUP BY p.id
        """, conn)

        produtos['lucro'] = (produtos['preco_venda'] - produtos['custo_producao']) * produtos['vendidos']

        st.dataframe(produtos)
        st.bar_chart(produtos.set_index('nome')['vendidos'])

    with tab3:
        st.subheader("Relatório de Clientes")
        clientes = pd.read_sql("""
            SELECT c.nome, c.celular, 
                   COUNT(v.id) as total_compras,
                   SUM(v.valor_total) as total_gasto
            FROM clientes c
            LEFT JOIN vendas v ON c.id = v.cliente_id
            GROUP BY c.id
        """, conn)

        st.dataframe(clientes)
        st.bar_chart(clientes.set_index('nome')['total_gasto'])

# =============================================
# FUNÇÃO PRINCIPAL
# =============================================
def main():
    # Inicia o servidor Flask em segundo plano
    

    # Agenda backups e inicia o scheduler em thread separada
    
   

    # Configuração do Streamlit
    st.set_page_config(
        page_title="Sistema de Vendas", 
        layout="wide",
        page_icon="🛒"
    )

    # Conexão com o banco de dados
    conn = criar_banco()

    # Menu lateral
    with st.sidebar:
        st.title("🛒 Sistema de Vendas")
        st.markdown("---")
        menu = st.radio("Menu", ["Clientes", "Produtos", "Vendas", "Relatórios"])
        st.markdown("---")
        st.markdown(f"**Online desde:** {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        if st.button("🔄 Atualizar Dados"):
            st.cache_data.clear()
            st.rerun()

        if st.button("💾 Criar Backup"):
            backup_db()

    # Navegação
    if menu == "Clientes":
        modulo_clientes(conn)
    elif menu == "Produtos":
        modulo_produtos(conn)
    elif menu == "Vendas":
        modulo_vendas(conn)
    elif menu == "Relatórios":
        modulo_relatorios(conn)

    # Fechar conexão
    conn.close()

if __name__ == "__main__":
    # Para desenvolvimento: recria o banco se necessário
    if os.path.exists('vendas.db'):
        os.remove('vendas.db')

    main()