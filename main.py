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
MONGO_URI = 'mongodb+srv://brunorodrigo:123Putao@cluster0.lrr3cgd.mongodb.net/saridulces?retryWrites=true&w=majority'

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
    st.title("👥 Gestão de Clientes")
    clientes_col = db['clientes']

    tab1, tab2, tab3 = st.tabs(["Cadastrar", "Listar/Editar", "Análises"])

    with tab1:
        st.subheader("Cadastro de Cliente")
        with st.form("form_cliente", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                nome = st.text_input("Nome Completo*", max_chars=100)
                data_nascimento = st.date_input("Data de Nascimento", 
                                              min_value=datetime(1900, 1, 1),
                                              max_value=datetime.now())
                cpf = st.text_input("CPF", 
                                   help="Formato: 123.456.789-00",
                                   max_chars=14)
                
            with col2:
                celular = st.text_input("Celular*", 
                                      max_chars=15,
                                      help="Formato: (99) 99999-9999")
                email = st.text_input("E-mail", 
                                    type="default",
                                    help="exemplo@dominio.com")
                
            endereco = st.text_area("Endereço Completo")
            observacoes = st.text_area("Observações/Notas")
            
            if st.form_submit_button("Cadastrar Cliente"):
                if not nome or not celular:
                    st.error("Campos obrigatórios (*) não preenchidos!")
                else:
                    novo_cliente = {
                        "nome": nome,
                        "data_nascimento": data_nascimento,
                        "cpf": cpf if cpf else None,
                        "contato": {
                            "celular": celular,
                            "email": email if email else None
                        },
                        "endereco": endereco if endereco else None,
                        "observacoes": observacoes if observacoes else None,
                        "data_cadastro": datetime.now(),
                        "ultima_atualizacao": datetime.now(),
                        "status": "ativo",
                        "tipo": "consumidor_final",  # ['consumidor_final', 'revendedor', 'empresa']
                        "compras_realizadas": 0,
                        "total_gasto": 0.0
                    }
                    
                    try:
                        # Verifica se CPF já existe
                        if cpf:
                            existe = clientes_col.count_documents({"cpf": cpf}, limit=1)
                            if existe > 0:
                                st.warning("Já existe um cliente cadastrado com este CPF")
                                return
                        
                        result = clientes_col.insert_one(novo_cliente)
                        st.success(f"Cliente cadastrado com sucesso! ID: {result.inserted_id}")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar cliente: {str(e)}")

    with tab2:
        st.subheader("Clientes Cadastrados")
        
        # Filtros avançados
        with st.expander("🔍 Filtros", expanded=False):
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                filtro_nome = st.text_input("Filtrar por nome")
            with col_f2:
                filtro_status = st.selectbox(
                    "Status",
                    ["Todos", "Ativo", "Inativo"],
                    index=0
                )
            with col_f3:
                filtro_tipo = st.selectbox(
                    "Tipo de cliente",
                    ["Todos", "Consumidor Final", "Revendedor", "Empresa"],
                    index=0
                )
        
        # Construção da query
        query = {}
        if filtro_nome:
            query["nome"] = {"$regex": filtro_nome, "$options": "i"}
        if filtro_status != "Todos":
            query["status"] = "ativo" if filtro_status == "Ativo" else "inativo"
        if filtro_tipo != "Todos":
            tipo_map = {
                "Consumidor Final": "consumidor_final",
                "Revendedor": "revendedor",
                "Empresa": "empresa"
            }
            query["tipo"] = tipo_map[filtro_tipo]
        
        # Consulta com paginação
        clientes = list(clientes_col.find(query).sort("nome", 1).limit(100))
        
        if clientes:
            # Preparação dos dados para exibição
            dados = []
            for c in clientes:
                dados.append({
                    "ID": str(c["_id"]),
                    "Nome": c["nome"],
                    "Contato": f"{c['contato']['celular']}" + 
                              (f"\n{c['contato']['email']}" if c['contato'].get('email') else ""),
                    "Tipo": "Consumidor" if c["tipo"] == "consumidor_final" else c["tipo"].capitalize(),
                    "Cadastro": c["data_cadastro"].strftime("%d/%m/%Y"),
                    "Compras": c.get("compras_realizadas", 0),
                    "Total Gasto": f"R$ {c.get('total_gasto', 0):.2f}",
                    "Status": c["status"].capitalize()
                })
            
            df = pd.DataFrame(dados)
            
            # Estilo condicional
            def estilo_linha(row):
                estilo = []
                if row['Status'] == 'Inativo':
                    estilo.append('color: gray')
                elif row['Tipo'] == 'Revendedor':
                    estilo.append('color: blue')
                elif row['Tipo'] == 'Empresa':
                    estilo.append('color: green')
                return estilo * len(row)
            
            st.dataframe(
                df.style.apply(estilo_linha, axis=1),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ID": st.column_config.Column(disabled=True),
                    "Total Gasto": st.column_config.NumberColumn(format="R$ %.2f")
                }
            )
            
            # Edição detalhada
            with st.expander("✏️ Editar Cliente", expanded=False):
                cliente_editar = st.selectbox(
                    "Selecione o cliente para editar",
                    [c["_id"] for c in clientes],
                    format_func=lambda x: next(c["nome"] for c in clientes if c["_id"] == x)
                )
                
                if cliente_editar:
                    cliente = clientes_col.find_one({"_id": cliente_editar})
                    with st.form(f"form_editar_{cliente_editar}"):
                        col_e1, col_e2 = st.columns(2)
                        
                        with col_e1:
                            novo_nome = st.text_input("Nome", value=cliente["nome"])
                            novo_cpf = st.text_input("CPF", 
                                                    value=cliente.get("cpf", ""),
                                                    max_chars=14)
                            novo_status = st.selectbox(
                                "Status",
                                ["ativo", "inativo"],
                                index=0 if cliente["status"] == "ativo" else 1
                            )
                            
                        with col_e2:
                            novo_celular = st.text_input(
                                "Celular", 
                                value=cliente["contato"]["celular"],
                                max_chars=15
                            )
                            novo_email = st.text_input(
                                "E-mail", 
                                value=cliente["contato"].get("email", "")
                            )
                            novo_tipo = st.selectbox(
                                "Tipo de cliente",
                                ["consumidor_final", "revendedor", "empresa"],
                                index=["consumidor_final", "revendedor", "empresa"].index(cliente["tipo"])
                            )
                        
                        novo_endereco = st.text_area(
                            "Endereço", 
                            value=cliente.get("endereco", "")
                        )
                        novas_obs = st.text_area(
                            "Observações", 
                            value=cliente.get("observacoes", "")
                        )
                        
                        if st.form_submit_button("Atualizar Cliente"):
                            atualizacao = {
                                "$set": {
                                    "nome": novo_nome,
                                    "cpf": novo_cpf if novo_cpf else None,
                                    "contato": {
                                        "celular": novo_celular,
                                        "email": novo_email if novo_email else None
                                    },
                                    "endereco": novo_endereco if novo_endereco else None,
                                    "observacoes": novas_obs if novas_obs else None,
                                    "status": novo_status,
                                    "tipo": novo_tipo,
                                    "ultima_atualizacao": datetime.now()
                                }
                            }
                            
                            try:
                                # Verifica se CPF já existe para outro cliente
                                if novo_cpf and novo_cpf != cliente.get("cpf", ""):
                                    existe = clientes_col.count_documents({
                                        "cpf": novo_cpf,
                                        "_id": {"$ne": cliente_editar}
                                    }, limit=1)
                                    if existe > 0:
                                        st.warning("CPF já cadastrado para outro cliente")
                                        return
                                
                                clientes_col.update_one(
                                    {"_id": cliente_editar},
                                    atualizacao
                                )
                                st.success("Cliente atualizado com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao atualizar cliente: {str(e)}")
        else:
            st.info("Nenhum cliente encontrado com os filtros selecionados.")

    with tab3:
        st.subheader("Análises de Clientes")
        
        col_a1, col_a2 = st.columns(2)
        
        with col_a1:
            st.metric("Total de Clientes", 
                     clientes_col.count_documents({}))
            st.metric("Clientes Ativos", 
                     clientes_col.count_documents({"status": "ativo"}))
            
            # Distribuição por tipo
            tipos = clientes_col.aggregate([
                {"$group": {"_id": "$tipo", "count": {"$sum": 1}}},
                {"$project": {"tipo": "$_id", "count": 1, "_id": 0}}
            ])
            
            df_tipos = pd.DataFrame(list(tipos))
            if not df_tipos.empty:
                df_tipos['tipo'] = df_tipos['tipo'].map({
                    "consumidor_final": "Consumidor",
                    "revendedor": "Revendedor",
                    "empresa": "Empresa"
                })
                st.bar_chart(df_tipos.set_index('tipo'))
        
        with col_a2:
            # Top clientes
            top_clientes = list(clientes_col.find(
                {"status": "ativo"}
            ).sort("total_gasto", -1).limit(5))
            
            if top_clientes:
                st.write("**Top Clientes por Valor Gasto**")
                for i, cliente in enumerate(top_clientes, 1):
                    st.write(f"{i}. {cliente['nome']} - R$ {cliente['total_gasto']:.2f}")
            
            # Evolução de cadastros
            evolucao = clientes_col.aggregate([
                {"$project": {
                    "ano_mes": {
                        "$dateToString": {
                            "format": "%Y-%m",
                            "date": "$data_cadastro"
                        }
                    }
                }},
                {"$group": {
                    "_id": "$ano_mes",
                    "total": {"$sum": 1}
                }},
                {"$sort": {"_id": 1}},
                {"$limit": 12}
            ])
            
            df_evolucao = pd.DataFrame(list(evolucao))
            if not df_evolucao.empty:
                st.line_chart(df_evolucao.set_index('_id'))
# =============================================
# MÓDULO DE PRODUTOS
# =============================================
def modulo_produtos(db):
    st.title("📦 Gestão de Produtos")
    produtos_col = db['produtos']

    tab1, tab2, tab3 = st.tabs(["Cadastrar", "Listar/Editar", "Gerenciar Estoque"])

    with tab1:
        st.subheader("Cadastro de Produto")
        with st.form("form_produto", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                nome = st.text_input("Nome do Produto*", max_chars=100)
                codigo = st.text_input("Código SKU", help="Código único de identificação")
                categoria = st.selectbox(
                    "Categoria*",
                    ["Doce", "Salgado", "Bebida", "Outros"],
                    index=0
                )
                
            with col2:
                preco_venda = st.number_input("Preço de Venda (R$)*", min_value=0.01, step=0.01, format="%.2f")
                custo_producao = st.number_input("Custo de Produção (R$)", min_value=0.0, step=0.01, format="%.2f", value=0.0)
                estoque_inicial = st.number_input("Estoque Inicial*", min_value=0, step=1, value=0)

            descricao = st.text_area("Descrição do Produto", height=100)
            ingredientes = st.text_area("Ingredientes/Composição")
            
            # Upload de imagem (opcional)
            imagem = st.file_uploader("Imagem do Produto", type=["jpg", "png", "jpeg"])
            
            if st.form_submit_button("Cadastrar Produto"):
                if not nome or not categoria:
                    st.error("Campos obrigatórios (*) não preenchidos!")
                else:
                    novo_produto = {
                        "nome": nome,
                        "codigo": codigo if codigo else None,
                        "categoria": categoria,
                        "descricao": descricao,
                        "ingredientes": ingredientes,
                        "preco_venda": float(preco_venda),
                        "custo_producao": float(custo_producao),
                        "estoque": int(estoque_inicial),
                        "data_cadastro": datetime.now(),
                        "ultima_atualizacao": datetime.now(),
                        "ativo": True,
                        "destaque": False
                    }
                    
                    try:
                        result = produtos_col.insert_one(novo_produto)
                        st.success(f"Produto cadastrado com sucesso! ID: {result.inserted_id}")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar produto: {str(e)}")

    with tab2:
        st.subheader("Produtos Cadastrados")
        
        # Filtros
        col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
        with col_filtro1:
            filtro_categoria = st.selectbox(
                "Filtrar por categoria",
                ["Todas"] + list(produtos_col.distinct("categoria")),
                index=0
            )
        with col_filtro2:
            filtro_estoque = st.selectbox(
                "Filtrar por estoque",
                ["Todos", "Em estoque", "Estoque baixo", "Sem estoque"],
                index=0
            )
        with col_filtro3:
            filtro_ativo = st.selectbox(
                "Status",
                ["Ativos", "Inativos", "Todos"],
                index=0
            )
        
        # Consulta com filtros
        query = {}
        if filtro_categoria != "Todas":
            query["categoria"] = filtro_categoria
        if filtro_estoque == "Em estoque":
            query["estoque"] = {"$gt": 0}
        elif filtro_estoque == "Estoque baixo":
            query["estoque"] = {"$lt": 10, "$gt": 0}
        elif filtro_estoque == "Sem estoque":
            query["estoque"] = 0
        if filtro_ativo == "Ativos":
            query["ativo"] = True
        elif filtro_ativo == "Inativos":
            query["ativo"] = False

        produtos = list(produtos_col.find(query).sort("nome", 1))
        
        if produtos:
            # Preparação dos dados para exibição
            dados = []
            for p in produtos:
                dados.append({
                    "ID": str(p["_id"]),
                    "Nome": p["nome"],
                    "Código": p.get("codigo", "-"),
                    "Categoria": p["categoria"],
                    "Preço": f"R$ {p['preco_venda']:.2f}",
                    "Custo": f"R$ {p.get('custo_producao', 0):.2f}",
                    "Estoque": p["estoque"],
                    "Status": "Ativo" if p.get("ativo", False) else "Inativo"
                })
            
            df = pd.DataFrame(dados)
            
            # Estilo condicional para estoque baixo
            def estilo_linha(row):
                estilo = []
                if row['Estoque'] == 0:
                    estilo.append('color: red')
                elif row['Estoque'] < 10:
                    estilo.append('color: orange')
                else:
                    estilo.append('color: green')
                return estilo * len(row)
            
            st.dataframe(
                df.style.apply(estilo_linha, axis=1),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ID": st.column_config.Column(disabled=True),
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Custo": st.column_config.NumberColumn(format="R$ %.2f")
                }
            )
            
            # Edição de produtos
            with st.expander("📝 Editar Produto", expanded=False):
                produto_editar = st.selectbox(
                    "Selecione o produto para editar",
                    [p["_id"] for p in produtos],
                    format_func=lambda x: next(p["nome"] for p in produtos if p["_id"] == x)
                )
                
                if produto_editar:
                    produto = produtos_col.find_one({"_id": produto_editar})
                    with st.form(f"form_editar_{produto_editar}"):
                        col_e1, col_e2 = st.columns(2)
                        
                        with col_e1:
                            novo_nome = st.text_input("Nome", value=produto["nome"])
                            novo_codigo = st.text_input("Código", value=produto.get("codigo", ""))
                            nova_categoria = st.selectbox(
                                "Categoria",
                                ["Doce", "Salgado", "Bebida", "Outros"],
                                index=["Doce", "Salgado", "Bebida", "Outros"].index(produto["categoria"])
                            )
                            
                        with col_e2:
                            novo_preco = st.number_input(
                                "Preço", 
                                min_value=0.01, 
                                step=0.01, 
                                value=float(produto["preco_venda"])
                            )
                            novo_custo = st.number_input(
                                "Custo", 
                                min_value=0.0, 
                                step=0.01, 
                                value=float(produto.get("custo_producao", 0))
                            )
                            novo_status = st.checkbox(
                                "Ativo", 
                                value=produto.get("ativo", True)
                            )
                        
                        nova_descricao = st.text_area(
                            "Descrição", 
                            value=produto.get("descricao", "")
                        )
                        novos_ingredientes = st.text_area(
                            "Ingredientes", 
                            value=produto.get("ingredientes", "")
                        )
                        
                        if st.form_submit_button("Atualizar Produto"):
                            atualizacao = {
                                "$set": {
                                    "nome": novo_nome,
                                    "codigo": novo_codigo if novo_codigo else None,
                                    "categoria": nova_categoria,
                                    "descricao": nova_descricao,
                                    "ingredientes": novos_ingredientes,
                                    "preco_venda": novo_preco,
                                    "custo_producao": novo_custo,
                                    "ativo": novo_status,
                                    "ultima_atualizacao": datetime.now()
                                }
                            }
                            
                            try:
                                produtos_col.update_one(
                                    {"_id": produto_editar},
                                    atualizacao
                                )
                                st.success("Produto atualizado com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao atualizar produto: {str(e)}")
        else:
            st.info("Nenhum produto encontrado com os filtros selecionados.")

    with tab3:
        st.subheader("Gerenciamento de Estoque")
        
        produtos_estoque = list(produtos_col.find({"ativo": True}).sort("nome", 1))
        
        if produtos_estoque:
            produto_selecionado = st.selectbox(
                "Selecione o produto",
                [p["_id"] for p in produtos_estoque],
                format_func=lambda x: next(f"{p['nome']} (Estoque: {p['estoque']})" for p in produtos_estoque if p["_id"] == x)
            )
            
            if produto_selecionado:
                produto = produtos_col.find_one({"_id": produto_selecionado})
                st.write(f"**Produto selecionado:** {produto['nome']}")
                st.write(f"**Estoque atual:** {produto['estoque']} unidades")
                
                col_m1, col_m2 = st.columns(2)
                
                with col_m1:
                    with st.form("form_entrada_estoque"):
                        entrada = st.number_input(
                            "Quantidade de entrada", 
                            min_value=1, 
                            step=1, 
                            value=1,
                            key="entrada"
                        )
                        motivo_entrada = st.text_input("Motivo da entrada (opcional)")
                        
                        if st.form_submit_button("Registrar Entrada"):
                            novo_estoque = produto["estoque"] + entrada
                            produtos_col.update_one(
                                {"_id": produto_selecionado},
                                {
                                    "$set": {"estoque": novo_estoque},
                                    "$push": {
                                        "movimentacoes": {
                                            "tipo": "entrada",
                                            "quantidade": entrada,
                                            "data": datetime.now(),
                                            "motivo": motivo_entrada if motivo_entrada else None,
                                            "responsavel": "Sistema"  # Poderia ser substituído por usuário logado
                                        }
                                    }
                                }
                            )
                            st.success(f"Entrada de {entrada} unidades registrada. Novo estoque: {novo_estoque}")
                            st.rerun()
                
                with col_m2:
                    with st.form("form_saida_estoque"):
                        saida = st.number_input(
                            "Quantidade de saída", 
                            min_value=1, 
                            step=1, 
                            max_value=produto["estoque"],
                            value=1,
                            key="saida"
                        )
                        motivo_saida = st.text_input("Motivo da saída (opcional)")
                        
                        if st.form_submit_button("Registrar Saída"):
                            novo_estoque = produto["estoque"] - saida
                            produtos_col.update_one(
                                {"_id": produto_selecionado},
                                {
                                    "$set": {"estoque": novo_estoque},
                                    "$push": {
                                        "movimentacoes": {
                                            "tipo": "saída",
                                            "quantidade": saida,
                                            "data": datetime.now(),
                                            "motivo": motivo_saida if motivo_saida else None,
                                            "responsavel": "Sistema"
                                        }
                                    }
                                }
                            )
                            st.success(f"Saída de {saida} unidades registrada. Novo estoque: {novo_estoque}")
                            st.rerun()
                
                # Histórico de movimentações
                if "movimentacoes" in produto and produto["movimentacoes"]:
                    st.subheader("Histórico de Movimentações")
                    historico = sorted(
                        produto["movimentacoes"], 
                        key=lambda x: x["data"], 
                        reverse=True
                    )[:20]  # Limita às últimas 20 movimentações
                    
                    for mov in historico:
                        cor = "green" if mov["tipo"] == "entrada" else "red"
                        st.markdown(
                            f"""
                            <div style="border-left: 4px solid {cor}; padding-left: 10px; margin: 5px 0;">
                                <b>{mov['tipo'].upper()}</b> - {mov['quantidade']} unidades<br>
                                <small>{mov['data'].strftime('%d/%m/%Y %H:%M')} | {mov.get('motivo', 'Sem motivo informado')}</small>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
        else:
            st.info("Nenhum produto ativo disponível para gerenciamento de estoque.")

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