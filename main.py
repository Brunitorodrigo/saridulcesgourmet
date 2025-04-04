import streamlit as st
import pandas as pd
from datetime import datetime
import os
import time
from pymongo import MongoClient
import certifi
from bson.objectid import ObjectId

# =============================================
# CONFIGURAÇÃO DO MONGODB ATLAS
# =============================================

# Configuração da conexão (substitua pela sua URI do MongoDB Atlas)
MONGO_URI = 'mongodb+srv://brunorodrigo:123Putao@cluster0.lrr3cgd.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'

# Conexão segura com o MongoDB Atlas
def get_database():
    try:
        client = MongoClient(
            MONGO_URI,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=5000,  # Timeout de 5 segundos
            connectTimeoutMS=30000,  # Timeout de conexão de 30 segundos
            socketTimeoutMS=30000  # Timeout de socket de 30 segundos
        )
        
        # Testa a conexão
        client.admin.command('ping')
        db = client.get_database()
        
        # Verifica se as coleções existem
        required_collections = ['clientes', 'produtos', 'vendas', 'itens_venda']
        for coll in required_collections:
            if coll not in db.list_collection_names():
                db.create_collection(coll)
                
        return db
        
    except Exception as e:
        st.error(f"Falha na conexão com o MongoDB: {str(e)}")
        st.error("Verifique:")
        st.error("1. Sua conexão com a internet")
        st.error("2. As credenciais do MongoDB Atlas")
        st.error("3. Se o cluster está ativo")
        st.stop()

# =============================================
# MÓDULO DE CLIENTES
# =============================================
def modulo_clientes(db):
    st.title("📋 Gestão de Clientes")
    clientes_col = db['clientes']

    try:
        # Consulta com tratamento de erro específico
        clientes = list(clientes_col.find({"ativo": True}).limit(100))  # Limite para evitar sobrecarga
        
        if not clientes:
            st.info("Nenhum cliente cadastrado ainda.")
            return
            
        # Processamento seguro dos ObjectIds
        clientes_processed = []
        for cliente in clientes:
            cliente['id'] = str(cliente['_id'])
            clientes_processed.append(cliente)
            
        df = pd.DataFrame(clientes_processed).drop(columns=['_id', 'ativo'], errors='ignore')
        st.dataframe(df)
        
    except Exception as e:
        st.error(f"Erro ao carregar clientes: {str(e)}")
        return

# =============================================
# MÓDULO DE PRODUTOS
# =============================================
def modulo_produtos(db):
    st.title("📦 Gestão de Produtos")
    produtos_col = db['produtos']

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
                    novo_produto = {
                        "nome": nome,
                        "descricao": descricao,
                        "preco_venda": preco,
                        "custo_producao": custo,
                        "estoque": estoque,
                        "data_cadastro": datetime.now(),
                        "ativo": True
                    }
                    try:
                        produtos_col.insert_one(novo_produto)
                        st.success("Produto cadastrado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao cadastrar produto: {e}")
                else:
                    st.error("Preencha os campos obrigatórios (*)")

    with tab2:
        st.subheader("Produtos Cadastrados")
        produtos = list(produtos_col.find({"ativo": True}))
        
        if produtos:
            df = pd.DataFrame(produtos)
            # Remover colunas não necessárias para exibição
            df = df.drop(columns=['_id', 'ativo'], errors='ignore')
            st.dataframe(df, use_container_width=True)

            # Edição de produtos
            with st.expander("Editar Produto"):
                produto_selecionado = st.selectbox(
                    "Selecione o produto",
                    options=[str(produto['_id']) for produto in produtos],
                    format_func=lambda x: f"{produtos_col.find_one({'_id': ObjectId(x)})['nome']} - Estoque: {produtos_col.find_one({'_id': ObjectId(x)})['estoque']}"
                )

                if produto_selecionado:
                    dados_produto = produtos_col.find_one({"_id": ObjectId(produto_selecionado)})

                    with st.form("form_editar_produto"):
                        novo_nome = st.text_input("Nome", value=dados_produto.get('nome', ''))
                        nova_descricao = st.text_area("Descrição", value=dados_produto.get('descricao', ''))
                        novo_preco = st.number_input(
                            "Preço", 
                            min_value=0.0, 
                            step=0.01, 
                            value=float(dados_produto.get('preco_venda', 0))
                        )
                        novo_custo = st.number_input(
                            "Custo", 
                            min_value=0.0, 
                            step=0.01, 
                            value=float(dados_produto.get('custo_producao', 0))
                        )
                        novo_estoque = st.number_input(
                            "Estoque", 
                            min_value=0, 
                            step=1, 
                            value=int(dados_produto.get('estoque', 0))
                        )

                        if st.form_submit_button("Atualizar"):
                            try:
                                produtos_col.update_one(
                                    {"_id": ObjectId(produto_selecionado)},
                                    {"$set": {
                                        "nome": novo_nome,
                                        "descricao": nova_descricao,
                                        "preco_venda": novo_preco,
                                        "custo_producao": novo_custo,
                                        "estoque": novo_estoque
                                    }}
                                )
                                st.success("Produto atualizado!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao atualizar produto: {e}")
        else:
            st.info("Nenhum produto cadastrado ainda.")

# =============================================
# MÓDULO DE VENDAS
# =============================================
def modulo_vendas(db):
    st.title("💰 Gestão de Vendas")
    vendas_col = db['vendas']
    itens_venda_col = db['itens_venda']
    clientes_col = db['clientes']
    produtos_col = db['produtos']

    tab1, tab2 = st.tabs(["Nova Venda", "Histórico"])

    with tab1:
        st.subheader("Registrar Nova Venda")

        # Selecionar cliente
        clientes = list(clientes_col.find({"ativo": True}))
        if not clientes:
            st.warning("Nenhum cliente cadastrado!")
            return

        cliente_id = st.selectbox(
            "Cliente*",
            options=[str(cliente['_id']) for cliente in clientes],
            format_func=lambda x: f"{clientes_col.find_one({'_id': ObjectId(x)})['nome']} - {clientes_col.find_one({'_id': ObjectId(x)})['celular']}"
        )

        # Adicionar produtos
        produtos = list(produtos_col.find({"ativo": True, "estoque": {"$gt": 0}}))
        if not produtos:
            st.warning("Nenhum produto disponível em estoque!")
            return

        itens_venda = st.session_state.get('itens_venda', [])

        col1, col2, col3 = st.columns(3)
        with col1:
            produto_id = st.selectbox(
                "Produto",
                options=[str(produto['_id']) for produto in produtos],
                format_func=lambda x: f"{produtos_col.find_one({'_id': ObjectId(x)})['nome']} - Estoque: {produtos_col.find_one({'_id': ObjectId(x)})['estoque']}"
            )
        with col2:
            quantidade = st.number_input("Quantidade", min_value=1, step=1, value=1)
        with col3:
            if st.button("Adicionar"):
                produto = produtos_col.find_one({"_id": ObjectId(produto_id)})
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
                    st.session_state['itens_venda'] = itens_venda
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
                    # Calcula lucro total
                    lucro_total = sum(
                        (item['preco_unitario'] - item['custo_unitario']) * item['quantidade']
                        for item in itens_venda
                    )

                    # Insere venda
                    nova_venda = {
                        "cliente_id": cliente_id,
                        "data_venda": datetime.now(),
                        "valor_total": total_venda,
                        "lucro_total": lucro_total,
                        "status": "finalizada"
                    }
                    venda_id = vendas_col.insert_one(nova_venda).inserted_id

                    # Insere itens da venda e atualiza estoque
                    for item in itens_venda:
                        # Insere item
                        itens_venda_col.insert_one({
                            "venda_id": str(venda_id),
                            "produto_id": item['produto_id'],
                            "quantidade": item['quantidade'],
                            "preco_unitario": item['preco_unitario'],
                            "custo_unitario": item['custo_unitario']
                        })

                        # Atualiza estoque
                        produtos_col.update_one(
                            {"_id": ObjectId(item['produto_id'])},
                            {"$inc": {"estoque": -item['quantidade']}}
                        )

                    st.success("Venda registrada com sucesso!")
                    st.balloons()
                    # Limpa os itens da venda após finalizar
                    del st.session_state['itens_venda']
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao registrar venda: {e}")

    with tab2:
        st.subheader("Histórico de Vendas")
        pipeline = [
            {
                "$lookup": {
                    "from": "clientes",
                    "localField": "cliente_id",
                    "foreignField": "_id",
                    "as": "cliente"
                }
            },
            {"$unwind": "$cliente"},
            {"$sort": {"data_venda": -1}}
        ]
        vendas = list(vendas_col.aggregate(pipeline))
        
        if vendas:
            # Prepara dados para exibição
            vendas_data = []
            for venda in vendas:
                vendas_data.append({
                    "id": str(venda['_id']),
                    "cliente": venda['cliente']['nome'],
                    "data_venda": venda['data_venda'],
                    "valor_total": venda['valor_total'],
                    "lucro_total": venda['lucro_total']
                })
            
            df_vendas = pd.DataFrame(vendas_data)
            st.dataframe(df_vendas, use_container_width=True)

            # Detalhes da venda selecionada
            venda_selecionada = st.selectbox(
                "Selecione uma venda para detalhar",
                options=[venda['id'] for venda in vendas_data],
                format_func=lambda x: f"Venda {x} - {next(v['cliente'] for v in vendas_data if v['id'] == x)} - R$ {next(v['valor_total'] for v in vendas_data if v['id'] == x):.2f}"
            )

            if venda_selecionada:
                # Busca itens da venda
                pipeline_itens = [
                    {
                        "$match": {"venda_id": venda_selecionada}
                    },
                    {
                        "$lookup": {
                            "from": "produtos",
                            "localField": "produto_id",
                            "foreignField": "_id",
                            "as": "produto"
                        }
                    },
                    {
                        "$unwind": "$produto"
                    }
                ]
                itens = list(itens_venda_col.aggregate(pipeline_itens))
                
                if itens:
                    itens_data = []
                    for item in itens:
                        itens_data.append({
                            "produto": item['produto']['nome'],
                            "quantidade": item['quantidade'],
                            "preco_unitario": item['preco_unitario'],
                            "subtotal": item['quantidade'] * item['preco_unitario']
                        })
                    
                    st.dataframe(pd.DataFrame(itens_data))
        else:
            st.info("Nenhuma venda registrada ainda.")

# =============================================
# MÓDULO DE RELATÓRIOS
# =============================================
def modulo_relatorios(db):
    st.title("📊 Relatórios")
    vendas_col = db['vendas']
    produtos_col = db['produtos']
    clientes_col = db['clientes']
    itens_venda_col = db['itens_venda']

    tab1, tab2, tab3 = st.tabs(["Vendas", "Produtos", "Clientes"])

    with tab1:
        st.subheader("Relatório de Vendas")

        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input("Data Início")
        with col2:
            data_fim = st.date_input("Data Fim")

        if st.button("Gerar Relatório"):
            pipeline = [
                {
                    "$match": {
                        "data_venda": {
                            "$gte": datetime.combine(data_inicio, datetime.min.time()),
                            "$lte": datetime.combine(data_fim, datetime.max.time())
                        }
                    }
                },
                {
                    "$lookup": {
                        "from": "clientes",
                        "localField": "cliente_id",
                        "foreignField": "_id",
                        "as": "cliente"
                    }
                },
                {
                    "$unwind": "$cliente"
                },
                {
                    "$sort": {"data_venda": 1}
                }
            ]
            vendas = list(vendas_col.aggregate(pipeline))
            
            if vendas:
                vendas_data = []
                for venda in vendas:
                    vendas_data.append({
                        "id": str(venda['_id']),
                        "cliente": venda['cliente']['nome'],
                        "data_venda": venda['data_venda'],
                        "valor_total": venda['valor_total'],
                        "lucro_total": venda['lucro_total']
                    })
                
                df_vendas = pd.DataFrame(vendas_data)
                st.dataframe(df_vendas)

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total de Vendas", f"R$ {df_vendas['valor_total'].sum():.2f}")
                with col2:
                    st.metric("Lucro Total", f"R$ {df_vendas['lucro_total'].sum():.2f}")

                st.bar_chart(df_vendas.set_index('data_venda')['valor_total'])
            else:
                st.warning("Nenhuma venda no período selecionado")

    with tab2:
        st.subheader("Relatório de Produtos")
        pipeline = [
            {
                "$lookup": {
                    "from": "itens_venda",
                    "localField": "_id",
                    "foreignField": "produto_id",
                    "as": "itens_venda"
                }
            },
            {
                "$project": {
                    "nome": 1,
                    "estoque": 1,
                    "preco_venda": 1,
                    "custo_producao": 1,
                    "vendidos": {"$sum": "$itens_venda.quantidade"},
                    "lucro": {
                        "$multiply": [
                            {"$subtract": ["$preco_venda", "$custo_producao"]},
                            {"$sum": "$itens_venda.quantidade"}
                        ]
                    }
                }
            }
        ]
        produtos = list(produtos_col.aggregate(pipeline))
        
        if produtos:
            df_produtos = pd.DataFrame(produtos)
            st.dataframe(df_produtos)
            st.bar_chart(df_produtos.set_index('nome')['vendidos'])
        else:
            st.info("Nenhum produto com vendas registradas.")

    with tab3:
        st.subheader("Relatório de Clientes")
        pipeline = [
            {
                "$lookup": {
                    "from": "vendas",
                    "localField": "_id",
                    "foreignField": "cliente_id",
                    "as": "vendas"
                }
            },
            {
                "$project": {
                    "nome": 1,
                    "celular": 1,
                    "total_compras": {"$size": "$vendas"},
                    "total_gasto": {"$sum": "$vendas.valor_total"}
                }
            }
        ]
        clientes = list(clientes_col.aggregate(pipeline))
        
        if clientes:
            df_clientes = pd.DataFrame(clientes)
            st.dataframe(df_clientes)
            st.bar_chart(df_clientes.set_index('nome')['total_gasto'])
        else:
            st.info("Nenhum cliente com compras registradas.")

# =============================================
# FUNÇÃO PRINCIPAL
# =============================================
def main():
    # Configuração do Streamlit
    st.set_page_config(
        page_title="Sistema de Vendas", 
        layout="wide",
        page_icon="🛒"
    )

    # Conexão com o MongoDB Atlas
    db = get_database()
    if db is None:
        st.error("Não foi possível conectar ao banco de dados. Verifique sua conexão com a internet e as credenciais do MongoDB.")
        return

    # Menu lateral
    with st.sidebar:
        st.title("🛒 Sistema de Vendas")
        st.markdown("---")
        menu = st.radio("Menu", ["Clientes", "Produtos", "Vendas", "Relatórios"])
        st.markdown("---")
        st.markdown(f"**Online desde:** {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        if st.button("🔄 Atualizar Dados"):
            st.rerun()

    # Navegação
    if menu == "Clientes":
        modulo_clientes(db)
    elif menu == "Produtos":
        modulo_produtos(db)
    elif menu == "Vendas":
        modulo_vendas(db)
    elif menu == "Relatórios":
        modulo_relatorios(db)

if __name__ == "__main__":
    main()