import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta, time as dt_time
import os
import time as pytime
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

    # Função para converter date para datetime (para o MongoDB)
    def date_to_datetime(date_obj):
        return datetime.combine(date_obj, dt_time.min)

    # Função para formatar exibição de datas
    def format_date(dt):
        return dt.strftime("%d/%m/%Y") if dt else "Não informado"

    # Layout principal com abas
    tab1, tab2 = st.tabs(["📝 Cadastrar", "📋 Listar/Editar"])

    # Aba de Cadastro
    with tab1:
        st.subheader("Cadastrar Novo Cliente")
        with st.form("form_cliente", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                nome = st.text_input("Nome Completo*", key="nome_cadastro")
                data_nascimento = st.date_input(
                    "Data de Nascimento",
                    min_value=date(1900, 1, 1),
                    max_value=datetime.now().date(),
                    format="DD/MM/YYYY"
                )
                cpf = st.text_input("CPF",
                                    help="Formato: 123.456.789-00",
                                    max_chars=14,
                                    key="cpf_cadastro")

            with col2:
                celular = st.text_input("Celular*",
                                        max_chars=15,
                                        help="Formato: (99) 99999-9999",
                                        key="celular_cadastro")
                email = st.text_input("E-mail",
                                      type="default",
                                      help="exemplo@dominio.com",
                                      key="email_cadastro")

            endereco = st.text_area("Endereço Completo", key="endereco_cadastro")
            observacoes = st.text_area("Observações/Notas", key="obs_cadastro")

            if st.form_submit_button("Salvar Cliente", type="primary"):
                if not nome or not celular:
                    st.error("Campos obrigatórios (*) não preenchidos!")
                else:
                    try:
                        if cpf:
                            existe = clientes_col.count_documents({"cpf": cpf}, limit=1)
                            if existe > 0:
                                st.warning("Já existe um cliente cadastrado com este CPF")
                                return

                        novo_cliente = {
                            "nome": nome,
                            "data_nascimento": date_to_datetime(data_nascimento),
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
                            "tipo": "consumidor_final"
                        }

                        clientes_col.insert_one(novo_cliente)
                        st.success("Cliente cadastrado com sucesso!")
                        st.balloons()
                        pytime.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar cliente: {str(e)}")

    # Aba de Listagem/Edição
    with tab2:
        st.subheader("Clientes Cadastrados")

        try:
            clientes = list(clientes_col.find({"status": "ativo"}).sort("nome", 1))

            if not clientes:
                st.info("Nenhum cliente cadastrado ainda.")
                if st.button("Cadastrar Primeiro Cliente", type="primary", key="btn_cadastrar_primeiro"):
                    st.session_state.redirect_to_tab1 = True
                    st.rerun()
            else:
                dados = []
                for cliente in clientes:
                    dados.append({
                        "ID": str(cliente["_id"]),
                        "Nome": cliente["nome"],
                        "Nascimento": format_date(cliente["data_nascimento"]),
                        "CPF": cliente.get("cpf", "Não informado"),
                        "Celular": cliente["contato"]["celular"],
                        "E-mail": cliente["contato"].get("email", "Não informado"),
                        "Cadastro": format_date(cliente["data_cadastro"]),
                        "Tipo": "Consumidor" if cliente["tipo"] == "consumidor_final" else cliente["tipo"].capitalize()
                    })

                df = pd.DataFrame(dados)
                st.dataframe(
                    df,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "ID": st.column_config.Column(disabled=True),
                        "Nascimento": st.column_config.DateColumn(format="DD/MM/YYYY"),
                        "Cadastro": st.column_config.DateColumn(format="DD/MM/YYYY")
                    }
                )

                # Seção de Edição
                st.subheader("Editar Cliente")
                cliente_selecionado = st.selectbox(
                    "Selecione o cliente para editar",
                    options=[cliente["_id"] for cliente in clientes],
                    format_func=lambda x: next(cliente["nome"] for cliente in clientes if cliente["_id"] == x),
                    key="select_editar"
                )

                if cliente_selecionado:
                    cliente = clientes_col.find_one({"_id": cliente_selecionado})
                    with st.form("form_editar_cliente"):
                        col_e1, col_e2 = st.columns(2)

                        with col_e1:
                            novo_nome = st.text_input("Nome", value=cliente["nome"], key="nome_editar")
                            nova_data_nasc = st.date_input(
                                "Data Nascimento",
                                value=cliente["data_nascimento"].date(),
                                min_value=date(1900, 1, 1),
                                max_value=datetime.now().date(),
                                format="DD/MM/YYYY",
                                key="data_editar"
                            )
                            novo_cpf = st.text_input(
                                "CPF",
                                value=cliente.get("cpf", ""),
                                max_chars=14,
                                key="cpf_editar"
                            )

                        with col_e2:
                            novo_celular = st.text_input(
                                "Celular",
                                value=cliente["contato"]["celular"],
                                max_chars=15,
                                key="celular_editar"
                            )
                            novo_email = st.text_input(
                                "E-mail",
                                value=cliente["contato"].get("email", ""),
                                key="email_editar"
                            )
                            novo_tipo = st.selectbox(
                                "Tipo de cliente",
                                ["consumidor_final", "revendedor", "empresa"],
                                index=["consumidor_final", "revendedor", "empresa"].index(cliente["tipo"]),
                                key="tipo_editar"
                            )

                        novo_endereco = st.text_area("Endereço", value=cliente.get("endereco", ""), key="endereco_editar")
                        novas_obs = st.text_area("Observações", value=cliente.get("observacoes", ""), key="obs_editar")

                        if st.form_submit_button("Atualizar Cliente", type="primary"):
                            atualizacao = {
                                "$set": {
                                    "nome": novo_nome,
                                    "data_nascimento": date_to_datetime(nova_data_nasc),
                                    "cpf": novo_cpf if novo_cpf else None,
                                    "contato": {
                                        "celular": novo_celular,
                                        "email": novo_email if novo_email else None
                                    },
                                    "endereco": novo_endereco if novo_endereco else None,
                                    "observacoes": novas_obs if novas_obs else None,
                                    "tipo": novo_tipo,
                                    "ultima_atualizacao": datetime.now()
                                }
                            }

                            try:
                                if novo_cpf and novo_cpf != cliente.get("cpf", ""):
                                    existe = clientes_col.count_documents({
                                        "cpf": novo_cpf,
                                        "_id": {"$ne": cliente_selecionado}
                                    }, limit=1)
                                    if existe > 0:
                                        st.warning("CPF já cadastrado para outro cliente")
                                        return

                                clientes_col.update_one({"_id": cliente_selecionado}, atualizacao)
                                st.success("Cliente atualizado com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao atualizar cliente: {str(e)}")

                # Seção de Exclusão (inativação)
                st.subheader("Remover Cliente")
                cliente_remover = st.selectbox(
                    "Selecione o cliente para remover",
                    options=[cliente["_id"] for cliente in clientes],
                    format_func=lambda x: next(cliente["nome"] for cliente in clientes if cliente["_id"] == x),
                    key="select_remover"
                )

                if cliente_remover and st.button("Confirmar Remoção", type="primary"):
                    try:
                        clientes_col.update_one(
                            {"_id": cliente_remover},
                            {"$set": {"status": "inativo"}}
                        )
                        st.success("Cliente marcado como inativo!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao remover cliente: {str(e)}")

        except Exception as e:
            st.error(f"Erro ao carregar clientes: {str(e)}")
            st.button("Tentar novamente", key="reload_clientes")

    # Redirecionamento para aba de cadastro se necessário
    if st.session_state.get('redirect_to_tab1', False):
        st.session_state.redirect_to_tab1 = False
        st.experimental_set_query_params(tab="📝 Cadastrar")
        st.rerun()
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
# =============================================
# MÓDULO DE VENDAS (atualização)
# =============================================
def modulo_vendas(db):
    st.title("💰 Gestão de Vendas")
    
    # Acessa as coleções necessárias
    vendas_col = db['vendas']
    itens_col = db['itens_venda']
    clientes_col = db['clientes']
    produtos_col = db['produtos']
    
    # Abas principais
    tab1, tab2, tab3, tab4 = st.tabs(["Nova Venda", "Histórico", "Relatórios", "Editar Venda"])

    # [Manter todo o código existente das abas 1, 2 e 3...]

    with tab4:
        st.subheader("Editar Venda Existente")
        
        # Filtro para selecionar a venda
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            data_inicio = st.date_input("Data inicial", 
                                      value=datetime.now() - timedelta(days=30),
                                      key="edit_data_inicio")
        with col_f2:
            data_fim = st.date_input("Data final", 
                                   value=datetime.now(),
                                   key="edit_data_fim")
        
        if st.button("Buscar Vendas"):
            filtro_data = {
                "data_venda": {
                    "$gte": datetime.combine(data_inicio, datetime.min.time()),
                    "$lte": datetime.combine(data_fim, datetime.max.time())
                }
            }
            st.session_state.vendas_para_editar = list(vendas_col.find(filtro_data).sort("data_venda", -1))
        
        if 'vendas_para_editar' in st.session_state and st.session_state.vendas_para_editar:
            vendas_lista = st.session_state.vendas_para_editar
            venda_selecionada = st.selectbox(
                "Selecione a venda para editar",
                options=[str(v["_id"]) for v in vendas_lista],
                format_func=lambda x: next(
                    f"{v['data_venda'].strftime('%d/%m/%Y %H:%M')} - {clientes_col.find_one({'_id': ObjectId(v['cliente_id'])})['nome']} - R$ {v['valor_total']:.2f}"
                    for v in vendas_lista if str(v["_id"]) == x
                )
            )
            
            if venda_selecionada:
                venda = vendas_col.find_one({"_id": ObjectId(venda_selecionada)})
                cliente = clientes_col.find_one({"_id": ObjectId(venda["cliente_id"])})
                itens_venda = list(itens_col.find({"venda_id": venda_selecionada}))
                
                st.write(f"**Cliente:** {cliente['nome']}")
                st.write(f"**Data da Venda:** {venda['data_venda'].strftime('%d/%m/%Y %H:%M')}")
                st.write(f"**Valor Total:** R$ {venda['valor_total']:.2f}")
                st.write(f"**Status:** {venda['status']}")
                
                st.subheader("Itens da Venda")
                
                # Carrega os produtos disponíveis
                produtos_disponiveis = list(produtos_col.find({"ativo": True}).sort("nome", 1))
                
                # Formulário de edição
                with st.form("form_editar_venda"):
                    novos_itens = []
                    valor_total = 0
                    lucro_total = 0
                    
                    for idx, item in enumerate(itens_venda):
                        produto = produtos_col.find_one({"_id": ObjectId(item["produto_id"])})
                        col1, col2, col3, col4 = st.columns([4, 2, 2, 1])
                        
                        with col1:
                            st.write(f"**{produto['nome']}**")
                            st.write(f"Estoque atual: {produto['estoque'] + item['quantidade']}")
                        with col2:
                            nova_quantidade = st.number_input(
                                "Quantidade",
                                min_value=0,
                                value=item["quantidade"],
                                key=f"qtd_{idx}"
                            )
                        with col3:
                            novo_preco = st.number_input(
                                "Preço unitário",
                                min_value=0.01,
                                value=float(item["preco_unitario"]),
                                step=0.01,
                                format="%.2f",
                                key=f"preco_{idx}"
                            )
                        with col4:
                            if st.button("❌", key=f"remover_{idx}"):
                                # Marca o item para remoção
                                st.session_state[f"remover_{idx}"] = True
                        
                        if nova_quantidade > 0 and not st.session_state.get(f"remover_{idx}", False):
                            subtotal = nova_quantidade * novo_preco
                            custo = nova_quantidade * item["custo_unitario"]
                            novos_itens.append({
                                "produto_id": item["produto_id"],
                                "quantidade": nova_quantidade,
                                "preco_unitario": novo_preco,
                                "custo_unitario": item["custo_unitario"],
                                "subtotal": subtotal,
                                "item_original": item
                            })
                            valor_total += subtotal
                            lucro_total += (novo_preco - item["custo_unitario"]) * nova_quantidade
                    
                    # Adicionar novo item
                    st.subheader("Adicionar Novo Item")
                    col_add1, col_add2, col_add3 = st.columns([3, 2, 2])
                    with col_add1:
                        novo_produto_id = st.selectbox(
                            "Produto",
                            options=[str(p["_id"]) for p in produtos_disponiveis],
                            format_func=lambda x: next(
                                f"{p['nome']} (Estoque: {p['estoque']})" 
                                for p in produtos_disponiveis 
                                if str(p["_id"]) == x
                            ),
                            key="novo_produto"
                        )
                    with col_add2:
                        nova_qtd = st.number_input("Quantidade", min_value=1, value=1, key="nova_qtd")
                    with col_add3:
                        novo_preco_add = st.number_input(
                            "Preço unitário",
                            min_value=0.01,
                            value=next(
                                p["preco_venda"] 
                                for p in produtos_disponiveis 
                                if str(p["_id"]) == novo_produto_id
                            ),
                            step=0.01,
                            format="%.2f",
                            key="novo_preco_add"
                        )
                    
                    if st.form_submit_button("Salvar Alterações"):
                        try:
                            with st.spinner("Atualizando venda..."):
                                # Processa as alterações nos itens
                                for item in novos_itens:
                                    # Calcula a diferença na quantidade
                                    diff = item["quantidade"] - item["item_original"]["quantidade"]
                                    
                                    if diff != 0:
                                        # Atualiza o estoque
                                        produtos_col.update_one(
                                            {"_id": ObjectId(item["produto_id"])},
                                            {"$inc": {"estoque": -diff}}
                                        )
                                    
                                    # Atualiza o item na venda
                                    itens_col.update_one(
                                        {"_id": item["item_original"]["_id"]},
                                        {
                                            "$set": {
                                                "quantidade": item["quantidade"],
                                                "preco_unitario": item["preco_unitario"],
                                                "subtotal": item["subtotal"]
                                            }
                                        }
                                    )
                                
                                # Remove os itens marcados para remoção
                                for idx, item in enumerate(itens_venda):
                                    if st.session_state.get(f"remover_{idx}", False):
                                        # Devolve ao estoque
                                        produtos_col.update_one(
                                            {"_id": ObjectId(item["produto_id"])},
                                            {"$inc": {"estoque": item["quantidade"]}}
                                        )
                                        # Remove o item
                                        itens_col.delete_one({"_id": item["_id"]})
                                
                                # Adiciona novos itens se houver
                                if novo_produto_id and nova_qtd > 0:
                                    produto_add = produtos_col.find_one({"_id": ObjectId(novo_produto_id)})
                                    
                                    # Verifica estoque
                                    if produto_add["estoque"] < nova_qtd:
                                        st.error(f"Estoque insuficiente para {produto_add['nome']}")
                                        return
                                    
                                    # Adiciona o item
                                    novo_item = {
                                        "venda_id": venda_selecionada,
                                        "produto_id": novo_produto_id,
                                        "quantidade": nova_qtd,
                                        "preco_unitario": novo_preco_add,
                                        "custo_unitario": produto_add.get("custo_producao", 0),
                                        "subtotal": nova_qtd * novo_preco_add
                                    }
                                    itens_col.insert_one(novo_item)
                                    
                                    # Atualiza estoque
                                    produtos_col.update_one(
                                        {"_id": ObjectId(novo_produto_id)},
                                        {"$inc": {"estoque": -nova_qtd}}
                                    )
                                    
                                    valor_total += novo_item["subtotal"]
                                    lucro_total += (novo_preco_add - produto_add.get("custo_producao", 0)) * nova_qtd
                                
                                # Atualiza a venda principal
                                vendas_col.update_one(
                                    {"_id": ObjectId(venda_selecionada)},
                                    {
                                        "$set": {
                                            "valor_total": valor_total,
                                            "lucro_total": lucro_total,
                                            "itens_count": len(novos_itens) + (1 if novo_produto_id and nova_qtd > 0 else 0),
                                            "ultima_atualizacao": datetime.now()
                                        }
                                    }
                                )
                                
                                st.success("Venda atualizada com sucesso!")
                                st.balloons()
                                pytime.sleep(1)
                                st.rerun()
                        
                        except Exception as e:
                            st.error(f"Erro ao atualizar venda: {str(e)}")
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