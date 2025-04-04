import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import time as pytime
from pymongo import MongoClient
import certifi
from bson.objectid import ObjectId
import hashlib
import base64
from io import BytesIO

# =============================================
# CONFIGURAÇÃO DO MONGODB ATLAS
# =============================================

MONGO_URI = 'mongodb+srv://brunorodrigo:123Putao@cluster0.lrr3cgd.mongodb.net/saridulces?retryWrites=true&w=majority'

def get_database():
    try:
        client = MongoClient(
            MONGO_URI,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000
        )
        
        client.admin.command('ping')
        db = client.get_database()
        
        required_collections = ['clientes', 'produtos', 'vendas', 'itens_venda', 'configuracoes', 'usuarios']
        for coll in required_collections:
            if coll not in db.list_collection_names():
                db.create_collection(coll)
                
                # Cria usuário admin padrão se a coleção for nova
                if coll == 'usuarios':
                    db.usuarios.insert_one({
                        "username": "admin",
                        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
                        "nome": "Administrador",
                        "email": "admin@sistema.com",
                        "nivel_acesso": "admin",
                        "data_criacao": datetime.now(),
                        "ultimo_login": None,
                        "ativo": True
                    })
                
        return db
        
    except Exception as e:
        st.error(f"Falha na conexão com o MongoDB: {str(e)}")
        st.error("Verifique sua conexão com a internet e as credenciais.")
        st.stop()

# =============================================
# SISTEMA DE AUTENTICAÇÃO
# =============================================

def inicializar_autenticacao():
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False
    if 'usuario_atual' not in st.session_state:
        st.session_state.usuario_atual = None
    if 'tentativas_login' not in st.session_state:
        st.session_state.tentativas_login = 0
    if 'pagina_atual' not in st.session_state:
        st.session_state.pagina_atual = "menu"

def verificar_credenciais(db, username, password):
    usuario = db.usuarios.find_one({"username": username, "ativo": True})
    if usuario:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if usuario['password_hash'] == password_hash:
            return usuario
    return None

def pagina_login(db):
    st.title("🔐 Login - Sistema de Vendas")
    
    with st.form("form_login"):
        username = st.text_input("Usuário", placeholder="Digite seu nome de usuário")
        password = st.text_input("Senha", placeholder="Digite sua senha", type="password")
        
        if st.form_submit_button("Entrar"):
            if st.session_state.tentativas_login >= 3:
                st.error("Número máximo de tentativas excedido. Tente novamente mais tarde.")
                return
            
            usuario = verificar_credenciais(db, username, password)
            if usuario:
                st.session_state.autenticado = True
                st.session_state.usuario_atual = usuario
                st.session_state.tentativas_login = 0
                st.session_state.pagina_atual = "menu"
                
                # Atualiza último login no banco de dados
                db.usuarios.update_one(
                    {"_id": usuario["_id"]},
                    {"$set": {"ultimo_login": datetime.now()}}
                )
                
                st.success(f"Bem-vindo, {usuario['nome']}!")
                pytime.sleep(1)
                st.rerun()
            else:
                st.session_state.tentativas_login += 1
                st.error("Credenciais inválidas. Tente novamente.")
    
    if st.session_state.tentativas_login > 0:
        st.warning(f"Tentativas restantes: {3 - st.session_state.tentativas_login}")

def verificar_autenticacao(db):
    if not st.session_state.autenticado:
        pagina_login(db)
        st.stop()

# =============================================
# FUNÇÃO DE ALTERAÇÃO DE SENHA
# =============================================

def alterar_senha(db):
    verificar_autenticacao(db)
    st.title("🔑 Alterar Senha")
    
    with st.form("form_alterar_senha", clear_on_submit=True):
        senha_atual = st.text_input("Senha Atual", type="password")
        nova_senha = st.text_input("Nova Senha", type="password", 
                                 help="A senha deve ter pelo menos 6 caracteres")
        confirmar_senha = st.text_input("Confirmar Nova Senha", type="password")
        
        if st.form_submit_button("Salvar Alterações", type="primary"):
            # Verifica se a senha atual está correta
            senha_atual_hash = hashlib.sha256(senha_atual.encode()).hexdigest()
            if senha_atual_hash != st.session_state.usuario_atual["password_hash"]:
                st.error("Senha atual incorreta!")
                return
            
            # Valida a nova senha
            if nova_senha != confirmar_senha:
                st.error("As senhas não coincidem!")
                return
            
            if len(nova_senha) < 6:
                st.error("A senha deve ter pelo menos 6 caracteres!")
                return
            
            # Atualiza a senha no banco de dados
            nova_senha_hash = hashlib.sha256(nova_senha.encode()).hexdigest()
            db.usuarios.update_one(
                {"_id": st.session_state.usuario_atual["_id"]},
                {"$set": {"password_hash": nova_senha_hash}}
            )
            
            # Atualiza a sessão
            st.session_state.usuario_atual["password_hash"] = nova_senha_hash
            
            st.success("Senha alterada com sucesso!")
            st.balloons()
            pytime.sleep(2)
            st.session_state.pagina_atual = "menu"
            st.rerun()
    
    if st.button("Voltar ao Menu"):
        st.session_state.pagina_atual = "menu"
        st.rerun()

# =============================================
# MÓDULO DE USUÁRIOS
# =============================================

def modulo_usuarios(db):
    verificar_autenticacao(db)
    
    # Verificar se o usuário atual tem permissão para acessar este módulo
    if st.session_state.usuario_atual['nivel_acesso'] not in ['admin', 'gerente']:
        st.error("Você não tem permissão para acessar esta funcionalidade.")
        return
    
    st.title("👨‍💼 Gestão de Usuários")
    
    tab1, tab2 = st.tabs(["📋 Lista de Usuários", "➕ Cadastrar Usuário"])
    
    with tab1:
        st.subheader("Usuários Cadastrados")
        
        usuarios = list(db.usuarios.find().sort("nome", 1))
        
        if not usuarios:
            st.info("Nenhum usuário cadastrado.")
        else:
            dados = []
            for usuario in usuarios:
                dados.append({
                    "ID": str(usuario["_id"]),
                    "Nome": usuario["nome"],
                    "Usuário": usuario["username"],
                    "E-mail": usuario.get("email", "-"),
                    "Nível": usuario["nivel_acesso"].capitalize(),
                    "Último Login": format_date(usuario.get("ultimo_login")),
                    "Status": "Ativo" if usuario.get("ativo", False) else "Inativo",
                    "Ações": "Manter"
                })

            df = pd.DataFrame(dados)
            
            edited_df = st.data_editor(
                df,
                column_config={
                    "ID": st.column_config.Column(disabled=True),
                    "Ações": st.column_config.SelectboxColumn(
                        "Ações",
                        options=["Manter", "Editar", "Inativar"],
                        required=True
                    )
                },
                hide_index=True,
                use_container_width=True,
                key="editor_usuarios"
            )
            
            if not edited_df[edited_df['Ações'] == "Inativar"].empty:
                st.warning("⚠️ Atenção: Esta ação desativará o acesso do usuário!")
                if st.button("Confirmar Inativação", type="primary"):
                    for idx, row in edited_df[edited_df['Ações'] == "Inativar"].iterrows():
                        db.usuarios.update_one(
                            {"_id": ObjectId(row['ID'])},
                            {"$set": {"ativo": False}}
                        )
                    st.success("Usuários inativados com sucesso!")
                    st.rerun()
    
    with tab2:
        st.subheader("Cadastrar Novo Usuário")
        with st.form("form_usuario", clear_on_submit=True, border=True):
            col1, col2 = st.columns(2)
            
            with col1:
                nome = st.text_input("Nome Completo*", placeholder="Nome completo do usuário")
                username = st.text_input("Nome de Usuário*", placeholder="Nome para login")
                
            with col2:
                email = st.text_input("E-mail", placeholder="usuario@empresa.com")
                nivel_acesso = st.selectbox(
                    "Nível de Acesso*",
                    ["admin", "gerente", "operador"],
                    index=2
                )
            
            password = st.text_input("Senha*", placeholder="Digite uma senha forte", type="password")
            confirm_password = st.text_input("Confirmar Senha*", placeholder="Repita a senha", type="password")
            
            if st.form_submit_button("Cadastrar Usuário", type="primary"):
                if not nome or not username or not password or not confirm_password:
                    st.error("Campos obrigatórios (*) não preenchidos!")
                elif password != confirm_password:
                    st.error("As senhas não coincidem!")
                else:
                    # Verifica se o username já existe
                    if db.usuarios.count_documents({"username": username}, limit=1) > 0:
                        st.error("Nome de usuário já está em uso!")
                    else:
                        try:
                            novo_usuario = {
                                "nome": nome,
                                "username": username,
                                "email": email if email else None,
                                "password_hash": hashlib.sha256(password.encode()).hexdigest(),
                                "nivel_acesso": nivel_acesso,
                                "data_criacao": datetime.now(),
                                "ultimo_login": None,
                                "ativo": True
                            }

                            db.usuarios.insert_one(novo_usuario)
                            st.success("Usuário cadastrado com sucesso!")
                            st.balloons()
                            pytime.sleep(1.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao cadastrar usuário: {str(e)}")

# =============================================
# FUNÇÕES AUXILIARES
# =============================================

def format_date(dt):
    return dt.strftime("%d/%m/%Y %H:%M") if dt else "Não informado"

def format_currency(value):
    return f"R$ {value:,.2f}"

def date_to_datetime(date_obj):
    return datetime.combine(date_obj, datetime.min.time())

def generate_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Relatorio')
    writer.close()
    processed_data = output.getvalue()
    return processed_data

# =============================================
# MÓDULO DE CLIENTES
# =============================================

def modulo_clientes(db):
    verificar_autenticacao(db)
    st.title("👥 Gestão de Clientes")
    clientes_col = db['clientes']

    tab1, tab2 = st.tabs(["📝 Cadastrar Cliente", "📋 Lista de Clientes"])

    with tab1:
        st.subheader("Cadastro de Novo Cliente")
        with st.form("form_cliente", clear_on_submit=True, border=True):
            col1, col2 = st.columns(2)
            
            with col1:
                nome = st.text_input("Nome Completo*", placeholder="Nome completo do cliente")
                data_nascimento = st.date_input(
                    "Data de Nascimento",
                    min_value=date(1900, 1, 1),
                    max_value=datetime.now().date(),
                    format="DD/MM/YYYY"
                )
                cpf = st.text_input("CPF", placeholder="000.000.000-00", max_chars=14)
                
            with col2:
                celular = st.text_input("Celular*", placeholder="(00) 00000-0000", max_chars=15)
                email = st.text_input("E-mail", placeholder="cliente@exemplo.com")
                tipo_cliente = st.selectbox(
                    "Tipo de Cliente",
                    ["Consumidor Final", "Revendedor", "Empresa"],
                    index=0
                )
            
            endereco = st.text_area("Endereço Completo")
            observacoes = st.text_area("Observações/Notas")
            
            if st.form_submit_button("Salvar Cliente", type="primary"):
                if not nome or not celular:
                    st.error("Campos obrigatórios (*) não preenchidos!")
                else:
                    try:
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
                            "tipo": tipo_cliente.lower().replace(" ", "_"),
                            "compras_realizadas": 0,
                            "total_gasto": 0.0
                        }

                        clientes_col.insert_one(novo_cliente)
                        st.success("Cliente cadastrado com sucesso!")
                        st.balloons()
                        pytime.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar cliente: {str(e)}")

    with tab2:
        st.subheader("Clientes Cadastrados")
        
        with st.expander("🔍 Filtros", expanded=True):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                filtro_nome = st.text_input("Buscar por nome")
            with col_f2:
                filtro_status = st.selectbox(
                    "Status",
                    ["Ativos", "Inativos", "Todos"],
                    index=0
                )
        
        query = {}
        if filtro_nome:
            query["nome"] = {"$regex": filtro_nome, "$options": "i"}
        if filtro_status != "Todos":
            query["status"] = "ativo" if filtro_status == "Ativos" else "inativo"
            
        clientes = list(clientes_col.find(query).sort("nome", 1))
        
        if not clientes:
            st.info("Nenhum cliente encontrado com os critérios selecionados.")
            if st.button("Cadastrar Novo Cliente", type="primary"):
                st.session_state.redirect_to_tab1 = True
                st.rerun()
        else:
            dados = []
            for cliente in clientes:
                dados.append({
                    "ID": str(cliente["_id"]),
                    "Nome": cliente["nome"],
                    "Celular": cliente["contato"]["celular"],
                    "E-mail": cliente["contato"].get("email", "-"),
                    "Tipo": cliente["tipo"].replace("_", " ").title(),
                    "Status": "Ativo" if cliente["status"] == "ativo" else "Inativo",
                    "Compras": cliente.get("compras_realizadas", 0),
                    "Total Gasto": cliente.get("total_gasto", 0),
                    "Ações": "Manter"
                })

            df = pd.DataFrame(dados)
            
            edited_df = st.data_editor(
                df,
                column_config={
                    "ID": st.column_config.Column(disabled=True),
                    "Total Gasto": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Ações": st.column_config.SelectboxColumn(
                        "Ações",
                        options=["Manter", "Editar", "Inativar"],
                        required=True
                    )
                },
                hide_index=True,
                use_container_width=True,
                key="editor_clientes"
            )
            
            if not edited_df[edited_df['Ações'] == "Inativar"].empty:
                st.warning("⚠️ Atenção: Esta ação marcará o cliente como inativo!")
                if st.button("Confirmar Inativação", type="primary"):
                    for idx, row in edited_df[edited_df['Ações'] == "Inativar"].iterrows():
                        clientes_col.update_one(
                            {"_id": ObjectId(row['ID'])},
                            {"$set": {"status": "inativo"}}
                        )
                    st.success("Clientes inativados com sucesso!")
                    st.rerun()

# =============================================
# MÓDULO DE PRODUTOS
# =============================================

def modulo_produtos(db):
    verificar_autenticacao(db)
    st.title("📦 Gestão de Produtos")
    produtos_col = db['produtos']

    tab1, tab2, tab3 = st.tabs(["📋 Lista de Produtos", "➕ Cadastrar Produto", "📊 Estoque"])

    with tab1:
        st.subheader("Produtos Cadastrados")
        
        with st.expander("🔍 Filtros", expanded=True):
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                filtro_nome = st.text_input("Buscar por nome")
            with col_f2:
                filtro_categoria = st.selectbox(
                    "Categoria",
                    ["Todas"] + list(produtos_col.distinct("categoria")),
                    index=0
                )
            with col_f3:
                filtro_estoque = st.selectbox(
                    "Estoque",
                    ["Todos", "Disponível", "Estoque Baixo", "Esgotado"],
                    index=0
                )
        
        query = {}
        if filtro_nome:
            query["nome"] = {"$regex": filtro_nome, "$options": "i"}
        if filtro_categoria != "Todas":
            query["categoria"] = filtro_categoria
        if filtro_estoque == "Disponível":
            query["estoque"] = {"$gt": 0}
        elif filtro_estoque == "Estoque Baixo":
            query["estoque"] = {"$gt": 0, "$lt": 10}
        elif filtro_estoque == "Esgotado":
            query["estoque"] = 0
            
        produtos = list(produtos_col.find(query).sort("nome", 1))
        
        if not produtos:
            st.info("Nenhum produto encontrado com os filtros selecionados.")
        else:
            dados = []
            for produto in produtos:
                dados.append({
                    "ID": str(produto["_id"]),
                    "Nome": produto["nome"],
                    "Código": produto.get("codigo", "-"),
                    "Categoria": produto["categoria"],
                    "Preço": produto["preco_venda"],
                    "Estoque": produto["estoque"],
                    "Status": "Ativo" if produto.get("ativo", False) else "Inativo",
                    "Ações": "Manter"
                })

            df = pd.DataFrame(dados)
            
            edited_df = st.data_editor(
                df,
                column_config={
                    "ID": st.column_config.Column(disabled=True),
                    "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Estoque": st.column_config.ProgressColumn(
                        "Estoque",
                        format="%d",
                        min_value=0,
                        max_value=100
                    ),
                    "Ações": st.column_config.SelectboxColumn(
                        "Ações",
                        options=["Manter", "Editar", "Inativar"],
                        required=True
                    )
                },
                hide_index=True,
                use_container_width=True,
                key="editor_produtos"
            )
            
            if not edited_df[edited_df['Ações'] == "Inativar"].empty:
                st.warning("⚠️ Atenção: Esta ação marcará o produto como inativo!")
                if st.button("Confirmar Inativação", type="primary"):
                    for idx, row in edited_df[edited_df['Ações'] == "Inativar"].iterrows():
                        produtos_col.update_one(
                            {"_id": ObjectId(row['ID'])},
                            {"$set": {"ativo": False}}
                        )
                    st.success("Produtos inativados com sucesso!")
                    st.rerun()

    with tab2:
        st.subheader("Cadastro de Produto")
        with st.form("form_produto", clear_on_submit=True, border=True):
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
            
            if st.form_submit_button("Cadastrar Produto", type="primary"):
                if not nome or not categoria or preco_venda <= 0:
                    st.error("Campos obrigatórios (*) não preenchidos corretamente!")
                else:
                    try:
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
                        
                        produtos_col.insert_one(novo_produto)
                        st.success("Produto cadastrado com sucesso!")
                        st.balloons()
                        pytime.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar produto: {str(e)}")

    with tab3:
        st.subheader("Gerenciamento de Estoque")
        
        produtos_estoque = list(produtos_col.find({"ativo": True}).sort("nome", 1))
        
        if not produtos_estoque:
            st.info("Nenhum produto ativo disponível para gerenciamento de estoque.")
        else:
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
                            value=1
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
                                            "responsavel": "Sistema"
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
                            value=1
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
                
                if "movimentacoes" in produto and produto["movimentacoes"]:
                    st.subheader("Histórico de Movimentações")
                    historico = sorted(
                        produto["movimentacoes"], 
                        key=lambda x: x["data"], 
                        reverse=True
                    )[:20]
                    
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

# =============================================
# MÓDULO DE VENDAS
# =============================================

def modulo_vendas(db):
    verificar_autenticacao(db)
    st.title("💰 Gestão de Vendas")
    
    vendas_col = db['vendas']
    itens_col = db['itens_venda']
    clientes_col = db['clientes']
    produtos_col = db['produtos']

    tab1, tab2, tab3 = st.tabs(["🛒 Nova Venda", "📜 Histórico", "📊 Relatórios"])

    with tab1:
        st.subheader("Registrar Nova Venda")
        
        # Seção 1: Seleção do Cliente
        clientes_ativos = list(clientes_col.find({"status": "ativo"}).sort("nome", 1))
        
        if not clientes_ativos:
            st.warning("Nenhum cliente cadastrado. Cadastre clientes antes de registrar vendas!")
            if st.button("Ir para Cadastro de Clientes ➡️"):
                st.session_state.menu = "Clientes"
                st.rerun()
            st.stop()
            
        col_c1, col_c2 = st.columns([4,1])
        with col_c1:
            cliente_id = st.selectbox(
                "Cliente*",
                options=[str(c["_id"]) for c in clientes_ativos],
                format_func=lambda x: next(c["nome"] for c in clientes_ativos if str(c["_id"]) == x),
                key="select_cliente_nova_venda"
            )
        with col_c2:
            if st.button("➕ Novo Cliente", use_container_width=True):
                st.session_state.menu = "Clientes"
                st.rerun()

        # Seção 2: Seleção de Produtos
        produtos_disponiveis = list(produtos_col.find({
            "ativo": True,
            "estoque": {"$gt": 0}
        }).sort("nome", 1))
        
        if not produtos_disponiveis:
            st.warning("Nenhum produto disponível em estoque!")
            if st.button("Ir para Gestão de Produtos ➡️"):
                st.session_state.menu = "Produtos"
                st.rerun()
            st.stop()

        # Inicializa os itens da venda na sessão
        if 'itens_venda' not in st.session_state:
            st.session_state.itens_venda = []
            
        # Interface para adicionar itens
        with st.container(border=True):
            col_p1, col_p2, col_p3 = st.columns([4, 2, 2])
            with col_p1:
                produto_id = st.selectbox(
                    "Selecione o produto",
                    options=[str(p["_id"]) for p in produtos_disponiveis],
                    format_func=lambda x: next(
                        f"{p['nome']} | Estoque: {p['estoque']} | R$ {p['preco_venda']:.2f}" 
                        for p in produtos_disponiveis 
                        if str(p["_id"]) == x
                    ),
                    key="select_produto_nova_venda"
                )
            with col_p2:
                quantidade = st.number_input(
                    "Quantidade",
                    min_value=1,
                    value=1,
                    key="qtd_produto_nova_venda"
                )
            with col_p3:
                st.write("")  # Espaçamento
                if st.button("➕ Adicionar", key="btn_add_item", use_container_width=True):
                    try:
                        produto = next(p for p in produtos_disponiveis if str(p["_id"]) == produto_id)
                        
                        if quantidade > produto['estoque']:
                            st.error(f"Estoque insuficiente! Disponível: {produto['estoque']}")
                        else:
                            # Verifica se o produto já está na venda
                            item_existente = next(
                                (item for item in st.session_state.itens_venda 
                                if item['produto_id'] == produto_id), None)
                            
                            if item_existente:
                                nova_quantidade = item_existente['quantidade'] + quantidade
                                if nova_quantidade > produto['estoque']:
                                    st.error(f"Quantidade total excede o estoque! Disponível: {produto['estoque']}")
                                else:
                                    item_existente['quantidade'] = nova_quantidade
                                    item_existente['subtotal'] = nova_quantidade * item_existente['preco_unitario']
                                    st.success(f"Quantidade de {produto['nome']} atualizada para {nova_quantidade}")
                            else:
                                st.session_state.itens_venda.append({
                                    'produto_id': produto_id,
                                    'nome': produto['nome'],
                                    'quantidade': quantidade,
                                    'preco_unitario': produto['preco_venda'],
                                    'custo_unitario': produto.get('custo_producao', 0),
                                    'subtotal': quantidade * produto['preco_venda']
                                })
                                st.success(f"{produto['nome']} adicionado à venda!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao adicionar produto: {str(e)}")

        # Lista de itens adicionados
        if st.session_state.itens_venda:
            st.subheader("Itens da Venda", divider="rainbow")
            
            # Cria DataFrame para exibição
            df_itens = pd.DataFrame(st.session_state.itens_venda)
            df_itens['Remover'] = False
            
            # Editor de dados com opção de remoção
            edited_df = st.data_editor(
                df_itens[['nome', 'quantidade', 'preco_unitario', 'subtotal', 'Remover']],
                column_config={
                    "preco_unitario": st.column_config.NumberColumn(
                        "Preço Unitário",
                        format="R$ %.2f"
                    ),
                    "subtotal": st.column_config.NumberColumn(
                        "Subtotal",
                        format="R$ %.2f"
                    ),
                    "Remover": st.column_config.CheckboxColumn(
                        "Remover?",
                        default=False
                    )
                },
                hide_index=True,
                use_container_width=True,
                key="editor_itens_venda"
            )
            
            # Processa remoção de itens marcados
            if not edited_df[edited_df['Remover']].empty:
                itens_manter = [item for idx, item in enumerate(st.session_state.itens_venda) 
                               if not edited_df.iloc[idx]['Remover']]
                st.session_state.itens_venda = itens_manter
                st.rerun()
            
            # Calcula totais
            total_venda = sum(item['subtotal'] for item in st.session_state.itens_venda)
            lucro_estimado = sum(
                (item['preco_unitario'] - item['custo_unitario']) * item['quantidade']
                for item in st.session_state.itens_venda
            )
            
            # Exibe totais
            col_res1, col_res2, col_res3 = st.columns(3)
            with col_res1:
                st.metric("Total Itens", len(st.session_state.itens_venda))
            with col_res2:
                st.metric("Total da Venda", f"R$ {total_venda:,.2f}")
            with col_res3:
                st.metric("Lucro Estimado", f"R$ {lucro_estimado:,.2f}")
            
            # Seção de Pagamento
            st.subheader("Forma de Pagamento", divider="rainbow")
            
            metodo_pagamento = st.radio(
                "Método de Pagamento*",
                ["Dinheiro", "Cartão de Crédito", "Cartão de Débito", "PIX", "Transferência Bancária"],
                horizontal=True
            )
            
            # Configurações específicas por método de pagamento
            detalhes_pagamento = {}
            
            if metodo_pagamento == "Dinheiro":
                valor_recebido = st.number_input(
                    "Valor Recebido (R$)*",
                    min_value=0.0,
                    value=float(total_venda),
                    step=1.0,
                    format="%.2f"
                )
                troco = valor_recebido - total_venda
                if troco >= 0:
                    st.success(f"Troco: R$ {troco:.2f}")
                    detalhes_pagamento["troco"] = troco
                else:
                    st.error("Valor insuficiente!")
                    st.stop()
            
            elif "Cartão" in metodo_pagamento:
                parcelas = st.selectbox(
                    "Número de Parcelas*",
                    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
                    index=0
                )
                valor_parcela = total_venda / parcelas
                st.write(f"💸 {parcelas}x de R$ {valor_parcela:.2f}")
                detalhes_pagamento["parcelas"] = parcelas
            
            elif metodo_pagamento == "PIX":
                st.write("🔳 **Chave PIX:** `vendas@sualoja.com.br`")
                st.image("https://via.placeholder.com/200?text=QR+CODE+PIX", width=200)
            
            elif metodo_pagamento == "Transferência Bancária":
                st.write("🏦 **Dados para Transferência:**")
                st.write("- Banco: **000** | Agência: **1234** | Conta: **56789-0**")
                comprovante = st.file_uploader("Envie o comprovante (opcional)", type=["jpg", "png", "pdf"])
                if comprovante:
                    detalhes_pagamento["comprovante"] = "Enviado"
            
            # Finalização da venda
            if st.button("✅ Finalizar Venda", type="primary", use_container_width=True):
                try:
                    with st.spinner("Processando venda..."):
                        # Cria a venda principal
                        nova_venda = {
                            "cliente_id": cliente_id,
                            "data_venda": datetime.now(),
                            "valor_total": total_venda,
                            "lucro_total": lucro_estimado,
                            "status": "concluída",
                            "itens_count": len(st.session_state.itens_venda),
                            "metodo_pagamento": metodo_pagamento.lower(),
                            "detalhes_pagamento": detalhes_pagamento
                        }
                        
                        # Insere a venda e obtém o ID
                        venda_id = vendas_col.insert_one(nova_venda).inserted_id
                        
                        # Registra os itens e atualiza estoque
                        for item in st.session_state.itens_venda:
                            # Item da venda
                            itens_col.insert_one({
                                "venda_id": str(venda_id),
                                "produto_id": item['produto_id'],
                                "quantidade": item['quantidade'],
                                "preco_unitario": item['preco_unitario'],
                                "custo_unitario": item['custo_unitario'],
                                "subtotal": item['subtotal']
                            })
                            
                            # Atualiza estoque
                            produtos_col.update_one(
                                {"_id": ObjectId(item['produto_id'])},
                                {"$inc": {"estoque": -item['quantidade']}}
                            )
                        
                        # Atualiza estatísticas do cliente
                        clientes_col.update_one(
                            {"_id": ObjectId(cliente_id)},
                            {
                                "$inc": {
                                    "compras_realizadas": 1,
                                    "total_gasto": total_venda
                                },
                                "$set": {
                                    "ultima_compra": datetime.now()
                                }
                            }
                        )
                        
                        # Sucesso - mostra resumo e limpa a venda
                        st.success("Venda registrada com sucesso!")
                        st.balloons()
                        
                        # Exibe resumo da venda
                        with st.expander("📝 Resumo da Venda", expanded=True):
                            cliente = clientes_col.find_one({"_id": ObjectId(cliente_id)})
                            st.write(f"**Cliente:** {cliente['nome']}")
                            st.write(f"**Data/Hora:** {datetime.now().strftime('%d/%m/%Y %H:%M')}")
                            st.write(f"**Total:** R$ {total_venda:,.2f}")
                            st.write(f"**Pagamento:** {metodo_pagamento}")
                            if metodo_pagamento == "Dinheiro":
                                st.write(f"**Valor Recebido:** R$ {valor_recebido:,.2f}")
                                st.write(f"**Troco:** R$ {troco:,.2f}")
                            elif "Cartão" in metodo_pagamento:
                                st.write(f"**Parcelas:** {parcelas}x de R$ {valor_parcela:,.2f}")
                            
                            st.write("**Itens:**")
                            for item in st.session_state.itens_venda:
                                st.write(f"- {item['nome']} ({item['quantidade']} x R$ {item['preco_unitario']:.2f})")
                        
                        # Limpa os itens da sessão
                        del st.session_state.itens_venda
                        pytime.sleep(3)
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Erro ao registrar venda: {str(e)}")
                    st.error("Nenhuma alteração foi aplicada no banco de dados.")

    with tab2:
        st.subheader("Histórico de Vendas")
        
        # Filtros
        with st.expander("🔎 Filtros", expanded=True):
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                data_inicio = st.date_input(
                    "Data inicial", 
                    value=datetime.now() - timedelta(days=30),
                    key="hist_data_inicio"
                )
            with col_f2:
                data_fim = st.date_input(
                    "Data final", 
                    value=datetime.now(),
                    key="hist_data_fim"
                )
            with col_f3:
                filtro_pagamento = st.selectbox(
                    "Forma de Pagamento",
                    ["Todas", "Dinheiro", "Cartão de Crédito", "Cartão de Débito", "PIX", "Transferência Bancária"],
                    index=0
                )
        
        # Aplica filtros
        filtro = {
            "data_venda": {
                "$gte": datetime.combine(data_inicio, datetime.min.time()),
                "$lte": datetime.combine(data_fim, datetime.max.time())
            }
        }
        
        if filtro_pagamento != "Todas":
            filtro["metodo_pagamento"] = filtro_pagamento.lower()
        
        try:
            # Consulta as vendas
            vendas = list(vendas_col.find(filtro).sort("data_venda", -1).limit(100))
            
            if not vendas:
                st.info("Nenhuma venda encontrada no período selecionado.")
            else:
                # Prepara dados para exibição
                dados_vendas = []
                for venda in vendas:
                    try:
                        cliente = clientes_col.find_one({"_id": ObjectId(venda["cliente_id"])})
                        dados_vendas.append({
                            "ID": str(venda["_id"]),
                            "Data": venda["data_venda"].strftime("%d/%m/%Y %H:%M"),
                            "Cliente": cliente["nome"] if cliente else "Cliente não encontrado",
                            "Valor Total": venda["valor_total"],
                            "Pagamento": venda["metodo_pagamento"].capitalize(),
                            "Status": venda["status"].capitalize(),
                            "Itens": venda["itens_count"],
                            "Ações": "Manter"
                        })
                    except:
                        continue
                
                # Cria DataFrame
                df_vendas = pd.DataFrame(dados_vendas)
                
                # Editor com opção de apagar
                edited_df = st.data_editor(
                    df_vendas,
                    column_config={
                        "Valor Total": st.column_config.NumberColumn(format="R$ %.2f"),
                        "Ações": st.column_config.SelectboxColumn(
                            "Ações",
                            options=["Manter", "Cancelar"],
                            required=True
                        )
                    },
                    hide_index=True,
                    use_container_width=True,
                    height=400,
                    key="editor_historico_vendas"
                )

                # Processa vendas marcadas para cancelar
                if not edited_df[edited_df['Ações'] == "Cancelar"].empty:
                    st.warning("⚠️ Atenção: Esta ação não pode ser desfeita!")
                    
                    if st.button("Confirmar Cancelamento", type="primary"):
                        with st.spinner("Processando cancelamento..."):
                            try:
                                for idx, row in edited_df[edited_df['Ações'] == "Cancelar"].iterrows():
                                    venda_id = row['ID']
                                    
                                    # 1. Recupera itens da venda
                                    itens_venda = list(itens_col.find({"venda_id": venda_id}))
                                    
                                    # 2. Devolve ao estoque
                                    for item in itens_venda:
                                        produtos_col.update_one(
                                            {"_id": ObjectId(item["produto_id"])},
                                            {"$inc": {"estoque": item["quantidade"]}}
                                        )
                                    
                                    # 3. Remove itens
                                    itens_col.delete_many({"venda_id": venda_id})
                                    
                                    # 4. Atualiza cliente
                                    valor_venda = vendas_col.find_one({"_id": ObjectId(venda_id)})["valor_total"]
                                    clientes_col.update_one(
                                        {"_id": ObjectId(venda["cliente_id"])},
                                        {
                                            "$inc": {
                                                "compras_realizadas": -1,
                                                "total_gasto": -valor_venda
                                            }
                                        }
                                    )
                                    
                                    # 5. Atualiza status da venda
                                    vendas_col.update_one(
                                        {"_id": ObjectId(venda_id)},
                                        {"$set": {"status": "cancelada"}}
                                    )
                                
                                st.success("Vendas canceladas com sucesso!")
                                st.balloons()
                                st.rerun()
                            
                            except Exception as e:
                                st.error(f"Erro ao cancelar: {str(e)}")

                # Detalhes da venda selecionada
                if len(dados_vendas) > 0:
                    venda_selecionada = st.selectbox(
                        "Selecione uma venda para detalhar",
                        options=[v["ID"] for v in dados_vendas if v["Ações"] == "Manter"],
                        format_func=lambda x: next(
                            f"{v['Data']} - {v['Cliente']} - R$ {v['Valor Total']:.2f}" 
                            for v in dados_vendas 
                            if v["ID"] == x
                        ),
                        key="select_venda_detalhe"
                    )
                    
                    if venda_selecionada:
                        try:
                            # Busca itens da venda
                            itens_venda = list(itens_col.find({"venda_id": venda_selecionada}))
                            
                            if itens_venda:
                                dados_itens = []
                                for item in itens_venda:
                                    produto = produtos_col.find_one({"_id": ObjectId(item["produto_id"])})
                                    dados_itens.append({
                                        "Produto": produto["nome"] if produto else "Produto não encontrado",
                                        "Quantidade": item["quantidade"],
                                        "Preço Unitário": item["preco_unitario"],
                                        "Subtotal": item["quantidade"] * item["preco_unitario"]
                                    })
                                
                                st.dataframe(
                                    pd.DataFrame(dados_itens),
                                    column_config={
                                        "Preço Unitário": st.column_config.NumberColumn(
                                            format="R$ %.2f"
                                        ),
                                        "Subtotal": st.column_config.NumberColumn(
                                            format="R$ %.2f"
                                        )
                                    },
                                    hide_index=True,
                                    use_container_width=True
                                )
                        except Exception as e:
                            st.error(f"Erro ao carregar itens da venda: {str(e)}")
        except Exception as e:
            st.error(f"Erro ao carregar histórico de vendas: {str(e)}")

    with tab3:
        st.subheader("Relatórios de Vendas")
        
        # Filtro por período
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            data_inicio_rel = st.date_input(
                "Data inicial", 
                value=datetime.now() - timedelta(days=30),
                key="rel_data_inicio"
            )
        with col_r2:
            data_fim_rel = st.date_input(
                "Data final", 
                value=datetime.now(),
                key="rel_data_fim"
            )
        with col_r3:
            filtro_pagamento_rel = st.selectbox(
                "Forma de Pagamento",
                ["Todas", "Dinheiro", "Cartão de Crédito", "Cartão de Débito", "PIX", "Transferência Bancária"],
                index=0,
                key="rel_pagamento"
            )
        
        # Métricas rápidas
        if st.button("Gerar Relatório", key="btn_gerar_relatorio"):
            try:
                with st.spinner("Processando dados..."):
                    # Filtro de data
                    filtro_rel = {
                        "data_venda": {
                            "$gte": datetime.combine(data_inicio_rel, datetime.min.time()),
                            "$lte": datetime.combine(data_fim_rel, datetime.max.time())
                        },
                        "status": "concluída"
                    }
                    
                    if filtro_pagamento_rel != "Todas":
                        filtro_rel["metodo_pagamento"] = filtro_pagamento_rel.lower()
                    
                    # Calcula métricas básicas
                    total_vendas = vendas_col.count_documents(filtro_rel)
                    
                    faturamento_result = vendas_col.aggregate([
                        {"$match": filtro_rel},
                        {"$group": {"_id": None, "total": {"$sum": "$valor_total"}}}
                    ])
                    faturamento_total = next(faturamento_result, {"total": 0})["total"]
                    
                    lucro_result = vendas_col.aggregate([
                        {"$match": filtro_rel},
                        {"$group": {"_id": None, "total": {"$sum": "$lucro_total"}}}
                    ])
                    lucro_total = next(lucro_result, {"total": 0})["total"]
                    
                    # Exibe métricas
                    col_met1, col_met2, col_met3 = st.columns(3)
                    with col_met1:
                        st.metric("Total de Vendas", total_vendas)
                    with col_met2:
                        st.metric("Faturamento Total", f"R$ {faturamento_total:,.2f}")
                    with col_met3:
                        st.metric("Lucro Total", f"R$ {lucro_total:,.2f}")
                    
                    # Gráfico de vendas por dia
                    st.subheader("Vendas por Dia")
                    vendas_diarias = vendas_col.aggregate([
                        {"$match": filtro_rel},
                        {"$project": {
                            "data": {"$dateToString": {"format": "%Y-%m-%d", "date": "$data_venda"}},
                            "valor_total": 1
                        }},
                        {"$group": {
                            "_id": "$data",
                            "total": {"$sum": "$valor_total"},
                            "qtd": {"$sum": 1}
                        }},
                        {"$sort": {"_id": 1}}
                    ])
                    
                    df_diario = pd.DataFrame(list(vendas_diarias))
                    if not df_diario.empty:
                        df_diario = df_diario.rename(columns={"_id": "Data", "total": "Valor", "qtd": "Quantidade"})
                        
                        tab1, tab2 = st.tabs(["Gráfico", "Tabela"])
                        with tab1:
                            st.bar_chart(df_diario.set_index("Data")["Valor"])
                        with tab2:
                            st.dataframe(
                                df_diario,
                                column_config={
                                    "Valor": st.column_config.NumberColumn(format="R$ %.2f")
                                },
                                hide_index=True
                            )
                    else:
                        st.info("Nenhum dado disponível para o período selecionado.")
                    
                    # Vendas por forma de pagamento
                    st.subheader("Vendas por Forma de Pagamento")
                    vendas_pagamento = vendas_col.aggregate([
                        {"$match": filtro_rel},
                        {"$group": {
                            "_id": "$metodo_pagamento",
                            "total": {"$sum": "$valor_total"},
                            "count": {"$sum": 1}
                        }},
                        {"$sort": {"total": -1}}
                    ])
                    
                    df_pagamento = pd.DataFrame(list(vendas_pagamento))
                    if not df_pagamento.empty:
                        df_pagamento = df_pagamento.rename(columns={"_id": "Pagamento", "total": "Valor", "count": "Quantidade"})
                        st.bar_chart(df_pagamento.set_index("Pagamento")["Valor"])
                    else:
                        st.info("Nenhum dado disponível sobre formas de pagamento.")
                    
                    # Top produtos
                    st.subheader("Produtos Mais Vendidos")
                    top_produtos = itens_col.aggregate([
                        {"$lookup": {
                            "from": "vendas",
                            "localField": "venda_id",
                            "foreignField": "_id",
                            "as": "venda"
                        }},
                        {"$unwind": "$venda"},
                        {"$match": filtro_rel},
                        {"$group": {
                            "_id": "$produto_id",
                            "total_vendido": {"$sum": "$quantidade"},
                            "faturamento": {"$sum": {"$multiply": ["$quantidade", "$preco_unitario"]}}
                        }},
                        {"$sort": {"total_vendido": -1}},
                        {"$limit": 5}
                    ])
                    
                    top_produtos = list(top_produtos)
                    if top_produtos:
                        for produto in top_produtos:
                            p = produtos_col.find_one({"_id": ObjectId(produto["_id"])})
                            if p:
                                with st.expander(f"**{p['nome']}**"):
                                    col_p1, col_p2 = st.columns(2)
                                    with col_p1:
                                        st.write(f"**Quantidade:** {produto['total_vendido']} unidades")
                                        st.write(f"**Faturamento:** R$ {produto['faturamento']:,.2f}")
                                    with col_p2:
                                        percentual = (produto['total_vendido'] / (produto['total_vendido'] + 10)) * 100
                                        st.progress(min(percentual, 100))
                    else:
                        st.info("Nenhum dado disponível sobre produtos vendidos.")
                    
                    # Exportação para Excel
                    st.subheader("Exportar Dados")
                    vendas_export = list(vendas_col.find(filtro_rel))
                    if vendas_export:
                        df_export = pd.DataFrame([{
                            "Data": v["data_venda"].strftime("%d/%m/%Y %H:%M"),
                            "Cliente": clientes_col.find_one({"_id": ObjectId(v["cliente_id"])})["nome"],
                            "Valor Total": v["valor_total"],
                            "Pagamento": v["metodo_pagamento"].capitalize(),
                            "Itens": v["itens_count"]
                        } for v in vendas_export])
                        
                        excel_data = generate_excel(df_export)
                        st.download_button(
                            label="📥 Exportar para Excel",
                            data=excel_data,
                            file_name=f"relatorio_vendas_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.warning("Nenhum dado para exportar")
            except Exception as e:
                st.error(f"Erro ao gerar relatório: {str(e)}")

# =============================================
# MÓDULO DE RELATÓRIOS
# =============================================

def modulo_relatorios(db):
    verificar_autenticacao(db)
    st.title("📊 Relatórios Avançados")
    
    vendas_col = db['vendas']
    produtos_col = db['produtos']
    clientes_col = db['clientes']
    itens_col = db['itens_venda']

    tab1, tab2, tab3 = st.tabs(["📈 Vendas", "📦 Produtos", "👥 Clientes"])

    with tab1:
        st.subheader("Relatório Analítico de Vendas")
        
        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input(
                "Data Início",
                value=datetime.now() - timedelta(days=30),
                key="rel_vendas_inicio"
            )
        with col2:
            data_fim = st.date_input(
                "Data Fim",
                value=datetime.now(),
                key="rel_vendas_fim"
            )
        
        if st.button("Gerar Relatório de Vendas", key="btn_rel_vendas"):
            try:
                pipeline = [
                    {
                        "$match": {
                            "data_venda": {
                                "$gte": datetime.combine(data_inicio, datetime.min.time()),
                                "$lte": datetime.combine(data_fim, datetime.max.time())
                            },
                            "status": "concluída"
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
                        "$sort": {"data_venda": -1}
                    }
                ]
                
                vendas = list(vendas_col.aggregate(pipeline))
                
                if vendas:
                    dados_vendas = []
                    for venda in vendas:
                        dados_vendas.append({
                            "ID": str(venda["_id"]),
                            "Data": venda["data_venda"].strftime("%d/%m/%Y %H:%M"),
                            "Cliente": venda["cliente"]["nome"],
                            "Valor Total": venda["valor_total"],
                            "Lucro": venda["lucro_total"],
                            "Pagamento": venda["metodo_pagamento"].capitalize(),
                            "Itens": venda["itens_count"]
                        })
                    
                    df_vendas = pd.DataFrame(dados_vendas)
                    
                    # Métricas resumidas
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total de Vendas", len(df_vendas))
                    with col2:
                        st.metric("Faturamento Total", f"R$ {df_vendas['Valor Total'].sum():,.2f}")
                    with col3:
                        st.metric("Lucro Total", f"R$ {df_vendas['Lucro'].sum():,.2f}")
                    
                    # Gráficos
                    st.subheader("Análise Temporal")
                    df_vendas['Data'] = pd.to_datetime(df_vendas['Data'], format='%d/%m/%Y %H:%M')
                    df_vendas['Dia'] = df_vendas['Data'].dt.date
                    
                    vendas_dia = df_vendas.groupby('Dia').agg({
                        'Valor Total': 'sum',
                        'ID': 'count'
                    }).rename(columns={'ID': 'Quantidade'})
                    
                    tab1, tab2 = st.tabs(["Valor", "Quantidade"])
                    with tab1:
                        st.line_chart(vendas_dia['Valor Total'])
                    with tab2:
                        st.bar_chart(vendas_dia['Quantidade'])
                    
                    # Análise por forma de pagamento
                    st.subheader("Por Forma de Pagamento")
                    pagamento_analise = df_vendas.groupby('Pagamento').agg({
                        'Valor Total': ['sum', 'count'],
                        'Lucro': 'sum'
                    })
                    st.dataframe(pagamento_analise)
                    
                    # Exportação
                    excel_data = generate_excel(df_vendas)
                    st.download_button(
                        label="📥 Exportar para Excel",
                        data=excel_data,
                        file_name=f"relatorio_vendas_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.info("Nenhuma venda encontrada no período selecionado.")
            except Exception as e:
                st.error(f"Erro ao gerar relatório: {str(e)}")

    with tab2:
        st.subheader("Relatório de Produtos")
        
        if st.button("Gerar Relatório de Produtos", key="btn_rel_produtos"):
            try:
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
                            "categoria": 1,
                            "preco_venda": 1,
                            "custo_producao": 1,
                            "estoque": 1,
                            "vendidos": {"$sum": "$itens_venda.quantidade"},
                            "faturamento": {
                                "$sum": {
                                    "$map": {
                                        "input": "$itens_venda",
                                        "as": "item",
                                        "in": {"$multiply": ["$$item.quantidade", "$$item.preco_unitario"]}
                                    }
                                }
                            },
                            "lucro": {
                                "$sum": {
                                    "$map": {
                                        "input": "$itens_venda",
                                        "as": "item",
                                        "in": {
                                            "$multiply": [
                                                {"$subtract": ["$$item.preco_unitario", "$custo_producao"]},
                                                "$$item.quantidade"
                                            ]
                                        }
                                    }
                                }
                            }
                        }
                    },
                    {
                        "$sort": {"vendidos": -1}
                    }
                ]
                
                produtos = list(produtos_col.aggregate(pipeline))
                
                if produtos:
                    df_produtos = pd.DataFrame(produtos)
                    
                    # Métricas resumidas
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total de Produtos", len(df_produtos))
                    with col2:
                        st.metric("Faturamento Total", f"R$ {df_produtos['faturamento'].sum():,.2f}")
                    with col3:
                        st.metric("Lucro Total", f"R$ {df_produtos['lucro'].sum():,.2f}")
                    
                    # Análise por categoria
                    st.subheader("Por Categoria")
                    categoria_analise = df_produtos.groupby('categoria').agg({
                        'vendidos': 'sum',
                        'faturamento': 'sum',
                        'lucro': 'sum'
                    })
                    st.dataframe(categoria_analise)
                    
                    # Top produtos
                    st.subheader("Top 10 Produtos Mais Vendidos")
                    top_produtos = df_produtos.sort_values('vendidos', ascending=False).head(10)
                    st.bar_chart(top_produtos.set_index('nome')['vendidos'])
                    
                    # Exportação
                    excel_data = generate_excel(df_produtos)
                    st.download_button(
                        label="📥 Exportar para Excel",
                        data=excel_data,
                        file_name=f"relatorio_produtos_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.info("Nenhum dado disponível sobre produtos.")
            except Exception as e:
                st.error(f"Erro ao gerar relatório: {str(e)}")

    with tab3:
        st.subheader("Relatório de Clientes")
        
        if st.button("Gerar Relatório de Clientes", key="btn_rel_clientes"):
            try:
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
                            "tipo": 1,
                            "total_compras": {"$size": "$vendas"},
                            "total_gasto": {"$sum": "$vendas.valor_total"},
                            "ultima_compra": {"$max": "$vendas.data_venda"}
                        }
                    },
                    {
                        "$sort": {"total_gasto": -1}
                    }
                ]
                
                clientes = list(clientes_col.aggregate(pipeline))
                
                if clientes:
                    df_clientes = pd.DataFrame(clientes)
                    
                    # Métricas resumidas
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total de Clientes", len(df_clientes))
                    with col2:
                        st.metric("Faturamento Total", f"R$ {df_clientes['total_gasto'].sum():,.2f}")
                    with col3:
                        st.metric("Compras Realizadas", df_clientes['total_compras'].sum())
                    
                    # Clientes mais valiosos
                    st.subheader("Top 10 Clientes (Por Valor Gasto)")
                    top_clientes = df_clientes.sort_values('total_gasto', ascending=False).head(10)
                    st.bar_chart(top_clientes.set_index('nome')['total_gasto'])
                    
                    # Análise por tipo de cliente
                    st.subheader("Por Tipo de Cliente")
                    tipo_analise = df_clientes.groupby('tipo').agg({
                        'total_compras': 'sum',
                        'total_gasto': 'sum'
                    })
                    st.dataframe(tipo_analise)
                    
                    # Exportação
                    excel_data = generate_excel(df_clientes)
                    st.download_button(
                        label="📥 Exportar para Excel",
                        data=excel_data,
                        file_name=f"relatorio_clientes_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.info("Nenhum dado disponível sobre clientes.")
            except Exception as e:
                st.error(f"Erro ao gerar relatório: {str(e)}")

# =============================================
# FUNÇÃO PRINCIPAL
# =============================================

def main():
    st.set_page_config(
        page_title="Sistema de Vendas",
        page_icon="🛒",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Inicializa sistema de autenticação
    inicializar_autenticacao()
    
    # Conexão com o banco de dados
    db = get_database()
    if db is None:
        st.error("Não foi possível conectar ao banco de dados. Verifique sua conexão com a internet e as credenciais do MongoDB.")
        return
    
    # Verifica autenticação antes de mostrar qualquer conteúdo
    if not st.session_state.autenticado:
        pagina_login(db)
        st.stop()
    
    # Menu lateral (apenas para usuários autenticados)
    with st.sidebar:
        st.title("🛒 Sistema de Vendas")
        st.markdown(f"**Usuário:** {st.session_state.usuario_atual['nome']}")
        st.markdown(f"**Nível:** {st.session_state.usuario_atual['nivel_acesso'].capitalize()}")
        st.markdown("---")
        
        opcoes_menu = ["👥 Clientes", "📦 Produtos", "💰 Vendas", "📊 Relatórios"]
        
        # Adiciona gestão de usuários apenas para administradores
        if st.session_state.usuario_atual['nivel_acesso'] in ['admin', 'gerente']:
            opcoes_menu.append("👨‍💼 Usuários")
        
        menu = st.radio(
            "Menu Principal",
            opcoes_menu,
            index=0
        )
        
        st.markdown("---")
        
        # Botão para alterar senha
        if st.button("🔑 Alterar Minha Senha", use_container_width=True):
            st.session_state.pagina_atual = "alterar_senha"
            st.rerun()
        
        # Botão para sair
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.autenticado = False
            st.session_state.usuario_atual = None
            st.rerun()
        
        st.markdown(f"**Data/Hora:** {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    # Navegação
    if 'pagina_atual' in st.session_state and st.session_state.pagina_atual == "alterar_senha":
        alterar_senha(db)
    elif menu == "👥 Clientes":
        modulo_clientes(db)
    elif menu == "📦 Produtos":
        modulo_produtos(db)
    elif menu == "💰 Vendas":
        modulo_vendas(db)
    elif menu == "📊 Relatórios":
        modulo_relatorios(db)
    elif menu == "👨‍💼 Usuários":
        modulo_usuarios(db)

if __name__ == "__main__":
    main()