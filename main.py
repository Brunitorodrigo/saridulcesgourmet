import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import time as pytime
from pymongo import MongoClient
from pymongo.errors import AutoReconnect, ConnectionFailure, ServerSelectionTimeoutError
import certifi
from bson.objectid import ObjectId
import hashlib
import base64
from io import BytesIO
import os
import time
from pymongo.errors import OperationFailure
from datetime import time
import time as module_time
# =============================================
# CONFIGURAÇÃO DO MONGODB ATLAS
# =============================================


MONGO_URI = st.secrets["MONGO_URI"]

def get_database(max_retries=3):
    """Função segura para obter conexão com o MongoDB"""
    
    # =============================================
    # VERIFICAÇÕES DE SEGURANÇA (adicionar esta parte)
    # =============================================
    if not MONGO_URI:
        raise ValueError("❌ String de conexão não configurada. Verifique seu arquivo .env ou variáveis de ambiente")
    
    if "mongodb+srv://" not in MONGO_URI:
        raise ValueError("❌ String de conexão inválida. Deve usar o formato mongodb+srv://")
    
    if any(cred in MONGO_URI for cred in ["username:password", "admin:admin", "root:root", "//:@"]):
        raise ValueError("❌ Credenciais padrão ou vazias detectadas na string de conexão")
    
    if len(MONGO_URI.split('@')[0].split(':')[1]) < 8:
        raise ValueError("❌ Senha muito curta (mínimo 8 caracteres)")
    
    # =============================================
    # CONEXÃO COM TRATAMENTO DE ERROS (mantenha o existente)
    # =============================================
    for attempt in range(max_retries):
        try:
            client = MongoClient(
                MONGO_URI,
                tlsCAFile=certifi.where(),  # Sempre use SSL
                connectTimeoutMS=15000,
                socketTimeoutMS=30000,
                serverSelectionTimeoutMS=15000,
                appname="SariDulcesApp",
                retryWrites=True,
                retryReads=True,
                readPreference='primaryPreferred',
                maxPoolSize=50,  # Limite de conexões
               # socketKeepAlive=True
            )
            
            # Teste de conexão seguro
            client.admin.command('ping')
            db = client.get_database('saridulces')
            
            # Verificação adicional de permissões
            if db.command('connectionStatus').get('authInfo', {}).get('authenticatedUsers', []) == []:
                raise ValueError("❌ Falha na autenticação com o banco de dados")
            
            return db
            
        except Exception as e:
            if attempt == max_retries - 1:
                st.error(f"🔒 Falha crítica de conexão: {str(e)}")
                st.error("⚠️ Verifique: 1) Sua conexão com a internet 2) Credenciais no .env 3) Acesso IP no MongoDB Atlas")
                st.stop()
            time.sleep(2 ** attempt)  # Backoff exponencial
            
        except OperationFailure as e:
            raise Exception(f"Erro de operação: {str(e)}")
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
    st.title("🔐 Login - Sari Dulces iGEST")
    
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
                        options=["Manter", "Editar", "Inativar", "Excluir"],
                        required=True
                    )
                },
                hide_index=True,
                use_container_width=True,
                key="editor_clientes"
            )
            
            # Processar ações selecionadas
            if not edited_df[edited_df['Ações'] != "Manter"].empty:
                st.warning("⚠️ Atenção: Ações em massa serão aplicadas!")
                
                col1, col2 = st.columns(2)
                
                # Ação de inativar
                if not edited_df[edited_df['Ações'] == "Inativar"].empty:
                    with col1:
                        if st.button("Confirmar Inativação", key="btn_inativar_clientes"):
                            for idx, row in edited_df[edited_df['Ações'] == "Inativar"].iterrows():
                                clientes_col.update_one(
                                    {"_id": ObjectId(row['ID'])},
                                    {"$set": {"status": "inativo"}}
                                )
                            st.success("Clientes inativados com sucesso!")
                            st.rerun()
                
                # Ação de excluir
                if not edited_df[edited_df['Ações'] == "Excluir"].empty:
                    with col2:
                        if st.button("Confirmar Exclusão", type="primary", key="btn_excluir_clientes"):
                            # Verificar se há vendas associadas aos clientes
                            clientes_para_excluir = edited_df[edited_df['Ações'] == "Excluir"]
                            tem_vendas = False
                            
                            for idx, row in clientes_para_excluir.iterrows():
                                cliente_id = row['ID']
                                # Verificar se existem vendas associadas
                                if db['vendas'].count_documents({"cliente_id": cliente_id}) > 0:
                                    tem_vendas = True
                                    break
                            
                            if tem_vendas:
                                st.error("Alguns clientes possuem vendas associadas e não podem ser excluídos!")
                            else:
                                for idx, row in clientes_para_excluir.iterrows():
                                    clientes_col.delete_one({"_id": ObjectId(row['ID'])})
                                st.success("Clientes excluídos com sucesso!")
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
                        options=["Manter", "Editar", "Inativar", "Excluir"],
                        required=True
                    )
                },
                hide_index=True,
                use_container_width=True,
                key="editor_produtos"
            )
            
            # Processar ações selecionadas
            if not edited_df[edited_df['Ações'] != "Manter"].empty:
                st.warning("⚠️ Atenção: Ações em massa serão aplicadas!")
                
                col1, col2 = st.columns(2)
                
                # Ação de inativar
                if not edited_df[edited_df['Ações'] == "Inativar"].empty:
                    with col1:
                        if st.button("Confirmar Inativação", key="btn_inativar_produtos"):
                            for idx, row in edited_df[edited_df['Ações'] == "Inativar"].iterrows():
                                produtos_col.update_one(
                                    {"_id": ObjectId(row['ID'])},
                                    {"$set": {"ativo": False}}
                                )
                            st.success("Produtos inativados com sucesso!")
                            st.rerun()
                
                # Ação de excluir
                if not edited_df[edited_df['Ações'] == "Excluir"].empty:
                    with col2:
                        if st.button("Confirmar Exclusão", type="primary", key="btn_excluir_produtos"):
                            # Verificar se há vendas associadas aos produtos
                            produtos_para_excluir = edited_df[edited_df['Ações'] == "Excluir"]
                            tem_vendas = False
                            
                            for idx, row in produtos_para_excluir.iterrows():
                                produto_id = row['ID']
                                # Verificar se existem itens de venda associados
                                if db['itens_venda'].count_documents({"produto_id": produto_id}) > 0:
                                    tem_vendas = True
                                    break
                            
                            if tem_vendas:
                                st.error("Alguns produtos possuem vendas associadas e não podem ser excluídos!")
                            else:
                                for idx, row in produtos_para_excluir.iterrows():
                                    produtos_col.delete_one({"_id": ObjectId(row['ID'])})
                                st.success("Produtos excluídos com sucesso!")
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

def modulo_vendas(db):
    verificar_autenticacao(db)
    st.title("💰 Gestão de Vendas")
    
    vendas_col = db['vendas']
    itens_col = db['itens_venda']
    clientes_col = db['clientes']
    produtos_col = db['produtos']
    entregas_col = db['entregas']

    tab1, tab2, tab3, tab4 = st.tabs(["🛒 Nova Venda", "📜 Histórico", "📊 Relatórios", "🚚 Entregas"])

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

        # Seção 2: Tipo de Entrega
        tipo_entrega = st.radio(
            "Tipo de Entrega",
            ["Retirada na Loja", "Entrega ao Cliente"],
            horizontal=True,
            key="tipo_entrega_venda"
        )

        # Seção 3: Seleção de Produtos
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
                            "detalhes_pagamento": detalhes_pagamento,
                            "tipo_entrega": tipo_entrega.lower().replace(" ", "_"),
                            "custo_entrega": 0.0  # Será atualizado quando agendar a entrega
                        }
                        
                        # Insere a venda e obtém o ID
                        venda_id = vendas_col.insert_one(nova_venda).inserted_id
                        st.session_state.ultima_venda = vendas_col.find_one({"_id": venda_id})
                        
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
                            st.write(f"**Tipo de Entrega:** {tipo_entrega}")
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

    # [Restante do código das outras abas (Histórico e Relatórios) permanece igual...]

    with tab4:
        st.subheader("Gestão de Entregas")
        
        # Verifica se há uma venda recente na sessão para agilizar o agendamento
        if 'ultima_venda' in st.session_state and st.session_state.ultima_venda.get('tipo_entrega', '') == 'entrega_ao_cliente':
            venda_para_entrega = st.session_state.ultima_venda
            st.success(f"Venda #{str(venda_para_entrega['_id'])[-6:]} pronta para agendamento de entrega!")
            
            with st.form("form_agendar_entrega_rapida"):
                col1, col2 = st.columns(2)
                with col1:
                    data_entrega = st.date_input(
                        "Data de Entrega*",
                        min_value=date.today(),
                        value=date.today() + timedelta(days=1))
                with col2:
                    horario_entrega = st.time_input(
                        "Horário*",
                        value=time(14, 0))
                
                custo_entrega = st.number_input(
                    "Custo da Entrega (R$)*",
                    min_value=0.0,
                    value=15.0,
                    step=0.01,
                    format="%.2f")
                
                if st.form_submit_button("Agendar Entrega"):
                    # Cria a entrega
                    nova_entrega = {
                        "venda_id": str(venda_para_entrega['_id']),
                        "data_entrega": datetime.combine(data_entrega, horario_entrega),
                        "status": "agendada",
                        "custo_entrega": float(custo_entrega),
                        "responsavel": st.session_state.usuario_atual['nome'],
                        "data_cadastro": datetime.now()
                    }
                    
                    entregas_col.insert_one(nova_entrega)
                    
                    # Atualiza a venda com o custo
                    vendas_col.update_one(
                        {"_id": venda_para_entrega['_id']},
                        {"$set": {"custo_entrega": float(custo_entrega)}}
                    )
                    
                    st.success("Entrega agendada com sucesso!")
                    del st.session_state.ultima_venda
                    st.rerun()
        
        # Lista de entregas pendentes
        st.subheader("Entregas Pendentes")
        
        entregas_pendentes = list(entregas_col.find({
            "status": {"$in": ["agendada", "em_rota"]}
        }).sort("data_entrega", 1))
        
        if not entregas_pendentes:
            st.info("Nenhuma entrega pendente no momento.")
        else:
            for entrega in entregas_pendentes:
                venda = vendas_col.find_one({"_id": ObjectId(entrega['venda_id'])})
                cliente = clientes_col.find_one({"_id": ObjectId(venda['cliente_id'])}) if venda else None
                
                with st.expander(f"Entrega #{str(entrega['_id'])[-6:]} - {entrega['data_entrega'].strftime('%d/%m/%Y %H:%M')}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Venda:** #{str(entrega['venda_id'])[-6:]}")
                        st.write(f"**Cliente:** {cliente['nome'] if cliente else 'Não encontrado'}")
                        st.write(f"**Status:** {entrega['status'].replace('_', ' ').title()}")
                    with col2:
                        st.write(f"**Valor da Venda:** R$ {venda['valor_total']:.2f}" if venda else "")
                        st.write(f"**Custo de Entrega:** R$ {entrega.get('custo_entrega', 0):.2f}")
                    
                    # Ações para a entrega
                    col_btn1, col_btn2, col_btn3 = st.columns(3)
                    with col_btn1:
                        if st.button(f"Marcar como Em Rota", key=f"em_rota_{entrega['_id']}"):
                            entregas_col.update_one(
                                {"_id": entrega['_id']},
                                {"$set": {"status": "em_rota"}}
                            )
                            st.rerun()
                    with col_btn2:
                        if st.button(f"Marcar como Entregue", key=f"entregue_{entrega['_id']}"):
                            entregas_col.update_one(
                                {"_id": entrega['_id']},
                                {"$set": {"status": "entregue"}}
                            )
                            st.rerun()
                    with col_btn3:
                        if st.button(f"Cancelar Entrega", key=f"cancelar_{entrega['_id']}"):
                            entregas_col.update_one(
                                {"_id": entrega['_id']},
                                {"$set": {"status": "cancelada"}}
                            )
                            st.rerun()

        # Todas as entregas agendadas
        st.subheader("Todas as Entregas")
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_data_inicio = st.date_input(
                "Data inicial",
                value=date.today() - timedelta(days=30),
                key="filtro_ent_data_inicio"
            )
        with col_f2:
            filtro_data_fim = st.date_input(
                "Data final",
                value=date.today(),
                key="filtro_ent_data_fim"
            )
        
        todas_entregas = list(entregas_col.find({
            "data_entrega": {
                "$gte": datetime.combine(filtro_data_inicio, datetime.min.time()),
                "$lte": datetime.combine(filtro_data_fim, datetime.max.time())
            }
        }).sort("data_entrega", -1))
        
        if not todas_entregas:
            st.info("Nenhuma entrega encontrada no período selecionado.")
        else:
            dados = []
            for entrega in todas_entregas:
                venda = vendas_col.find_one({"_id": ObjectId(entrega['venda_id'])})
                cliente = clientes_col.find_one({"_id": ObjectId(venda['cliente_id'])}) if venda else None
                
                dados.append({
                    "ID": str(entrega['_id']),
                    "Venda": f"#{str(entrega['venda_id'])[-6:]}",
                    "Cliente": cliente['nome'] if cliente else "Não encontrado",
                    "Data": entrega['data_entrega'].strftime('%d/%m/%Y %H:%M'),
                    "Status": entrega['status'].replace('_', ' ').title(),
                    "Custo": entrega.get('custo_entrega', 0)
                })
            
            st.dataframe(
                pd.DataFrame(dados),
                column_config={
                    "Custo": st.column_config.NumberColumn(format="R$ %.2f")
                },
                hide_index=True,
                use_container_width=True
            )
# =============================================
# MÓDULO DE ENTREGAS
# =============================================

def modulo_entregas(db):
    verificar_autenticacao(db)
    st.title("🚚 Gestão de Entregas (Avançado)")
    
    vendas_col = db['vendas']
    clientes_col = db['clientes']
    entregas_col = db['entregas']

    tab1, tab2 = st.tabs(["📅 Agenda de Entregas", "📊 Relatório"])

    with tab1:
        st.subheader("Agenda de Entregas")
        
        # Filtros
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            data_inicio = st.date_input(
                "Data inicial",
                value=date.today(),
                key="ent_data_inicio"
            )
        with col_f2:
            data_fim = st.date_input(
                "Data final",
                value=date.today() + timedelta(days=7),
                key="ent_data_fim"
            )
        with col_f3:
            filtro_status = st.selectbox(
                "Status",
                ["Todas", "Agendada", "Em Rota", "Entregue", "Cancelada"],
                index=0,
                key="filtro_status_entrega"
            )
        
        # Construir query de filtro
        query = {
            "data_entrega": {
                "$gte": datetime.combine(data_inicio, datetime.min.time()),
                "$lte": datetime.combine(data_fim, datetime.max.time())
            }
        }
        
        if filtro_status != "Todas":
            query["status"] = filtro_status.lower().replace(" ", "_")
        
        # Busca entregas no período
        entregas = list(entregas_col.find(query).sort("data_entrega", 1))
        
        if not entregas:
            st.info("Nenhuma entrega encontrada com os filtros selecionados.")
        else:
            # Prepara dados para exibição
            dados_entregas = []
            for entrega in entregas:
                try:
                    venda = vendas_col.find_one({"_id": ObjectId(entrega["venda_id"])})
                    cliente = clientes_col.find_one({"_id": ObjectId(venda["cliente_id"])}) if venda else None
                    
                    dados_entregas.append({
                        "ID": str(entrega["_id"]),
                        "Venda": f"#{str(entrega['venda_id'])[-6:]}",
                        "Cliente": cliente["nome"] if cliente else "Cliente não encontrado",
                        "Data Entrega": entrega["data_entrega"].strftime("%d/%m/%Y %H:%M"),
                        "Status": entrega["status"].replace("_", " ").title(),
                        "Valor": venda["valor_total"] if venda else 0,
                        "Endereço": entrega.get("endereco_entrega", "Retirada na loja"),
                        "Ações": "Manter"
                    })
                except:
                    continue

            df_entregas = pd.DataFrame(dados_entregas)
            
            edited_df = st.data_editor(
                df_entregas,
                column_config={
                    "ID": st.column_config.Column(disabled=True),
                    "Venda": st.column_config.Column(disabled=True),
                    "Valor": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Ações": st.column_config.SelectboxColumn(
                        "Ações",
                        options=["Manter", "Editar", "Em Rota", "Entregue", "Cancelar"],
                        required=True
                    )
                },
                hide_index=True,
                use_container_width=True,
                key="editor_entregas"
            )
            
            # Processar ações selecionadas
            if not edited_df[edited_df['Ações'] != "Manter"].empty:
                st.warning("⚠️ Atenção: Ações em massa serão aplicadas!")
                
                # Ação de editar
                if not edited_df[edited_df['Ações'] == "Editar"].empty:
                    for idx, row in edited_df[edited_df['Ações'] == "Editar"].iterrows():
                        st.session_state.editar_entrega_id = row['ID']
                        st.rerun()
                
                # Ações de status
                for acao in ["Em Rota", "Entregue", "Cancelar"]:
                    if not edited_df[edited_df['Ações'] == acao].empty:
                        if st.button(f"Confirmar '{acao}'", key=f"btn_{acao}"):
                            for idx, row in edited_df[edited_df['Ações'] == acao].iterrows():
                                novo_status = acao.lower().replace(" ", "_") if acao != "Cancelar" else "cancelada"
                                entregas_col.update_one(
                                    {"_id": ObjectId(row['ID'])},
                                    {"$set": {"status": novo_status}}
                                )
                            st.success(f"Status atualizado para '{acao}'!")
                            st.rerun()

    # Edição de entrega
    if 'editar_entrega_id' in st.session_state and st.session_state.editar_entrega_id:
        entrega = entregas_col.find_one({"_id": ObjectId(st.session_state.editar_entrega_id)})
        if entrega:
            venda = vendas_col.find_one({"_id": ObjectId(entrega["venda_id"])})
            cliente = clientes_col.find_one({"_id": ObjectId(venda["cliente_id"])}) if venda else None
            
            st.subheader("Editar Entrega")
            st.write(f"**Venda:** #{str(entrega['venda_id'])[-6:]}")
            st.write(f"**Cliente:** {cliente['nome'] if cliente else 'Não encontrado'}")
            
            with st.form("form_editar_entrega"):
                col1, col2 = st.columns(2)
                with col1:
                    nova_data = st.date_input(
                        "Data de Entrega",
                        value=entrega["data_entrega"].date(),
                        min_value=date.today()
                    )
                    novo_horario = st.time_input(
                        "Horário",
                        value=entrega["data_entrega"].time()
                    )
                with col2:
                    novo_status = st.selectbox(
                        "Status",
                        ["agendada", "em_rota", "entregue", "cancelada"],
                        index=["agendada", "em_rota", "entregue", "cancelada"].index(entrega["status"])
                    )
                    novo_custo = st.number_input(
                        "Custo da Entrega (R$)",
                        min_value=0.0,
                        value=float(entrega.get("custo_entrega", 0)),
                        step=0.01,
                        format="%.2f"
                    )
                
                observacoes = st.text_area(
                    "Observações",
                    value=entrega.get("observacoes", "")
                )
                
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.form_submit_button("Salvar Alterações"):
                        data_hora_entrega = datetime.combine(nova_data, novo_horario)
                        
                        atualizacao = {
                            "data_entrega": data_hora_entrega,
                            "status": novo_status,
                            "custo_entrega": novo_custo,
                            "observacoes": observacoes,
                            "ultima_atualizacao": datetime.now()
                        }
                        
                        entregas_col.update_one(
                            {"_id": ObjectId(st.session_state.editar_entrega_id)},
                            {"$set": atualizacao}
                        )
                        
                        # Atualiza custo na venda associada
                        if venda:
                            vendas_col.update_one(
                                {"_id": ObjectId(entrega["venda_id"])},
                                {"$set": {"custo_entrega": novo_custo}}
                            )
                        
                        st.success("Entrega atualizada com sucesso!")
                        del st.session_state.editar_entrega_id
                        module_time.sleep(1)
                        st.rerun()
                
                with col_b2:
                    if st.button("Cancelar"):
                        del st.session_state.editar_entrega_id
                        st.rerun()

    with tab2:
        st.subheader("Relatório de Entregas")
        
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            data_inicio_rel = st.date_input(
                "Data inicial",
                    value=date.today() - timedelta(days=30),
                key="rel_ent_data_inicio"
            )
        with col_r2:
            data_fim_rel = st.date_input(
                "Data final",
                    value=date.today(),  # Correção aplicada aqui
                key="rel_ent_data_fim"
            )
        
        if st.button("Gerar Relatório", key="btn_rel_entregas"):
            try:
                with st.spinner("Processando relatório..."):
                    # Filtro de período
                    filtro = {
                        "data_entrega": {
                            "$gte": datetime.combine(data_inicio_rel, datetime.min.time()),
                            "$lte": datetime.combine(data_fim_rel, datetime.max.time())
                        }
                    }
                    
                    # Busca entregas no período
                    entregas = list(entregas_col.find(filtro).sort("data_entrega", 1))
                    
                    if not entregas:
                        st.info("Nenhuma entrega encontrada no período selecionado.")
                    else:
                        # Processa dados para o relatório
                        dados = []
                        for entrega in entregas:
                            try:
                                venda = vendas_col.find_one({"_id": ObjectId(entrega["venda_id"])})
                                cliente = clientes_col.find_one({"_id": ObjectId(venda["cliente_id"])}) if venda else None
                                
                                dados.append({
                                    "Data": entrega["data_entrega"].strftime("%d/%m/%Y %H:%M"),
                                    "Venda": f"#{str(entrega['venda_id'])[-6:]}",
                                    "Cliente": cliente["nome"] if cliente else "Não encontrado",
                                    "Status": entrega["status"].replace("_", " ").title(),
                                    "Custo": entrega.get("custo_entrega", 0),
                                    "Responsável": entrega.get("responsavel", "Não informado")
                                })
                            except:
                                continue
                        
                        df_relatorio = pd.DataFrame(dados)
                        
                        # Métricas rápidas
                        col_m1, col_m2, col_m3 = st.columns(3)
                        with col_m1:
                            st.metric("Total de Entregas", len(entregas))
                        with col_m2:
                            custo_total = df_relatorio["Custo"].sum()
                            st.metric("Custo Total", f"R$ {custo_total:,.2f}")
                        with col_m3:
                            entregues = len([e for e in entregas if e["status"] == "entregue"])
                            st.metric("Taxa de Entrega", f"{(entregues/len(entregas)*100):.1f}%")
                        
                        # Agrupamento por status
                        st.subheader("Distribuição por Status")
                        status_counts = df_relatorio["Status"].value_counts()
                        st.bar_chart(status_counts)
                        
                        # Tabela detalhada
                        st.subheader("Detalhes das Entregas")
                        st.dataframe(
                            df_relatorio,
                            column_config={
                                "Custo": st.column_config.NumberColumn(format="R$ %.2f")
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                        
                        # Exportar para Excel
                        excel_data = generate_excel(df_relatorio)
                        st.download_button(
                            label="📥 Exportar para Excel",
                            data=excel_data,
                            file_name=f"relatorio_entregas_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
            except Exception as e:
                st.error(f"Erro ao gerar relatório: {str(e)}")

# =============================================
# MÓDULO DE RELATÓRIOS
# =============================================

def modulo_relatorios(db):
    verificar_autenticacao(db)
    st.title("📊 Painel Estratégico")
    
    vendas_col = db['vendas']
    produtos_col = db['produtos']
    clientes_col = db['clientes']
    itens_col = db['itens_venda']
    usuarios_col = db['usuarios']

    tab1, tab2, tab3 = st.tabs(["📈 Visão Geral", "📦 Produtos", "👥 Clientes"])

    with tab1:
        st.subheader("Visão Geral do Negócio")
        
        # Filtros por período
        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input(
                "Data Início",
                value=datetime.now() - timedelta(days=30),
                key="geral_inicio"
            )
        with col2:
            data_fim = st.date_input(
                "Data Fim",
                value=datetime.now(),
                key="geral_fim"
            )
        
        if st.button("Atualizar Relatório", key="btn_atualizar_geral"):
            try:
                # Filtro de período
                filtro_periodo = {
                    "data_venda": {
                        "$gte": datetime.combine(data_inicio, datetime.min.time()),
                        "$lte": datetime.combine(data_fim, datetime.max.time())
                    },
                    "status": "concluída"
                }
                
                # 1. Métricas Principais
                st.subheader("🔍 Métricas Principais")
                
                # Consultas principais
                total_vendas = vendas_col.count_documents(filtro_periodo)
                
                faturamento_result = vendas_col.aggregate([
                    {"$match": filtro_periodo},
                    {"$group": {"_id": None, "total": {"$sum": "$valor_total"}}}
                ])
                faturamento_total = next(faturamento_result, {"total": 0})["total"]
                
                lucro_result = vendas_col.aggregate([
                    {"$match": filtro_periodo},
                    {"$group": {"_id": None, "total": {"$sum": "$lucro_total"}}}
                ])
                lucro_total = next(lucro_result, {"total": 0})["total"]
                
                # Clientes ativos
                clientes_ativos = clientes_col.count_documents({"status": "ativo"})
                
                # Produtos ativos
                produtos_ativos = produtos_col.count_documents({"ativo": True})
                
                # Exibe métricas em colunas
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                with col_m1:
                    st.metric("Total de Vendas", total_vendas)
                with col_m2:
                    st.metric("Faturamento Total", f"R$ {faturamento_total:,.2f}")
                with col_m3:
                    st.metric("Lucro Total", f"R$ {lucro_total:,.2f}")
                with col_m4:
                    st.metric("Margem Líquida", f"{(lucro_total/faturamento_total*100 if faturamento_total > 0 else 0):.1f}%")
                
                col_m5, col_m6, col_m7, col_m8 = st.columns(4)
                with col_m5:
                    st.metric("Clientes Ativos", clientes_ativos)
                with col_m6:
                    st.metric("Produtos Ativos", produtos_ativos)
                with col_m7:
                    ticket_medio = faturamento_total/total_vendas if total_vendas > 0 else 0
                    st.metric("Ticket Médio", f"R$ {ticket_medio:,.2f}")
                with col_m8:
                    usuarios_ativos = usuarios_col.count_documents({"ativo": True})
                    st.metric("Usuários Ativos", usuarios_ativos)
                
                # 2. Análise Temporal
                st.subheader("📅 Análise Temporal")
                
                # Vendas por dia
                vendas_diarias = vendas_col.aggregate([
                    {"$match": filtro_periodo},
                    {"$project": {
                        "data": {"$dateToString": {"format": "%Y-%m-%d", "date": "$data_venda"}},
                        "valor_total": 1,
                        "lucro_total": 1
                    }},
                    {"$group": {
                        "_id": "$data",
                        "total_vendas": {"$sum": 1},
                        "total_faturamento": {"$sum": "$valor_total"},
                        "total_lucro": {"$sum": "$lucro_total"}
                    }},
                    {"$sort": {"_id": 1}}
                ])
                
                df_diario = pd.DataFrame(list(vendas_diarias))
                if not df_diario.empty:
                    df_diario['_id'] = pd.to_datetime(df_diario['_id'])
                    df_diario = df_diario.set_index('_id')
                    
                    tab1, tab2, tab3 = st.tabs(["Vendas", "Faturamento", "Lucro"])
                    with tab1:
                        st.line_chart(df_diario['total_vendas'])
                    with tab2:
                        st.line_chart(df_diario['total_faturamento'])
                    with tab3:
                        st.line_chart(df_diario['total_lucro'])
                else:
                    st.info("Nenhuma venda no período selecionado.")
                
                # 3. Métricas por Forma de Pagamento
                st.subheader("💳 Análise por Forma de Pagamento")
                
                pagamento_analise = vendas_col.aggregate([
                    {"$match": filtro_periodo},
                    {"$group": {
                        "_id": "$metodo_pagamento",
                        "total_vendas": {"$sum": 1},
                        "total_faturamento": {"$sum": "$valor_total"},
                        "total_lucro": {"$sum": "$lucro_total"}
                    }},
                    {"$addFields": {
                        "percentual_faturamento": {
                            "$multiply": [
                                {"$divide": ["$total_faturamento", faturamento_total]},
                                100
                            ]
                        },
                        "ticket_medio": {
                            "$divide": ["$total_faturamento", "$total_vendas"]
                        }
                    }},
                    {"$sort": {"total_faturamento": -1}}
                ])
                
                df_pagamento = pd.DataFrame(list(pagamento_analise))
                if not df_pagamento.empty:
                    df_pagamento = df_pagamento.rename(columns={
                        "_id": "Pagamento",
                        "total_vendas": "Vendas",
                        "total_faturamento": "Faturamento",
                        "total_lucro": "Lucro",
                        "percentual_faturamento": "% Faturamento",
                        "ticket_medio": "Ticket Médio"
                    })
                    
                    # Formata valores
                    df_pagamento['Faturamento'] = df_pagamento['Faturamento'].apply(lambda x: f"R$ {x:,.2f}")
                    df_pagamento['Lucro'] = df_pagamento['Lucro'].apply(lambda x: f"R$ {x:,.2f}")
                    df_pagamento['% Faturamento'] = df_pagamento['% Faturamento'].apply(lambda x: f"{x:.1f}%")
                    df_pagamento['Ticket Médio'] = df_pagamento['Ticket Médio'].apply(lambda x: f"R$ {x:,.2f}")
                    
                    st.dataframe(
                        df_pagamento,
                        column_order=["Pagamento", "Vendas", "Faturamento", "Lucro", "% Faturamento", "Ticket Médio"],
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("Nenhum dado disponível sobre formas de pagamento.")
                
                # 4. Indicadores de Desempenho
                st.subheader("📊 Indicadores de Desempenho")
                
                # Comparativo com período anterior
                # Calcula a diferença de dias entre data_fim e data_inicio
                dias_periodo = (data_fim - data_inicio).days

                # Define o período anterior com a mesma duração do período atual
                periodo_anterior = {
                            "$gte": datetime.combine(data_inicio - timedelta(days=dias_periodo), datetime.min.time()),
                        "$lte": datetime.combine(data_inicio - timedelta(days=1), datetime.max.time())
                                        }
                
                faturamento_anterior = next(vendas_col.aggregate([
                    {"$match": {"data_venda": periodo_anterior, "status": "concluída"}},
                    {"$group": {"_id": None, "total": {"$sum": "$valor_total"}}}
                ]), {"total": 0})["total"]
                
                variacao_faturamento = ((faturamento_total - faturamento_anterior) / faturamento_anterior * 100) if faturamento_anterior > 0 else 0
                
                col_i1, col_i2, col_i3 = st.columns(3)
                with col_i1:
                    st.metric(
                        "Faturamento vs Período Anterior",
                        f"R$ {faturamento_total:,.2f}",
                        delta=f"{variacao_faturamento:.1f}%",
                        delta_color="normal" if variacao_faturamento >= 0 else "inverse"
                    )
                with col_i2:
                    produtos_mais_vendidos = list(itens_col.aggregate([
                        {"$lookup": {
                            "from": "vendas",
                            "localField": "venda_id",
                            "foreignField": "_id",
                            "as": "venda"
                        }},
                        {"$unwind": "$venda"},
                        {"$match": filtro_periodo},
                        {"$group": {
                            "_id": "$produto_id",
                            "total_vendido": {"$sum": "$quantidade"}
                        }},
                        {"$sort": {"total_vendido": -1}},
                        {"$limit": 1}
                    ]))
                    
                    if produtos_mais_vendidos:
                        produto = produtos_col.find_one({"_id": produtos_mais_vendidos[0]["_id"]})
                        st.metric(
                            "Produto Mais Vendido",
                            produto["nome"],
                            delta=f"{produtos_mais_vendidos[0]['total_vendido']} unidades"
                        )
                    else:
                        st.metric("Produto Mais Vendido", "Nenhum")
                with col_i3:
                    cliente_top = next(clientes_col.aggregate([
                        {"$lookup": {
                            "from": "vendas",
                            "localField": "_id",
                            "foreignField": "cliente_id",
                            "as": "vendas"
                        }},
                        {"$match": {"vendas.data_venda": filtro_periodo["data_venda"]}},
                        {"$project": {
                            "nome": 1,
                            "total_gasto": {"$sum": "$vendas.valor_total"}
                        }},
                        {"$sort": {"total_gasto": -1}},
                        {"$limit": 1}
                    ]), None)
                    
                    if cliente_top:
                        st.metric(
                            "Cliente Top",
                            cliente_top["nome"],
                            delta=f"R$ {cliente_top['total_gasto']:,.2f}"
                        )
                    else:
                        st.metric("Cliente Top", "Nenhum")
                
            except Exception as e:
                st.error(f"Erro ao gerar relatório: {str(e)}")

    with tab2:
        st.subheader("Análise de Produtos")
        
        if st.button("Atualizar Relatório de Produtos", key="btn_atualizar_produtos"):
            try:
                # 1. Métricas de Produtos
                st.subheader("📦 Métricas de Produtos")
                
                # Consultas principais
                pipeline_estoque = [
                    {"$match": {"ativo": True}},
                    {"$group": {
                        "_id": None,
                        "total_estoque": {"$sum": "$estoque"},
                        "valor_estoque": {"$sum": {"$multiply": ["$estoque", "$preco_venda"]}},
                        "custo_estoque": {"$sum": {"$multiply": ["$estoque", "$custo_producao"]}}
                    }}
                ]
                
                estoque_data = next(produtos_col.aggregate(pipeline_estoque), {
                    "total_estoque": 0,
                    "valor_estoque": 0,
                    "custo_estoque": 0
                })
                
                # Vendas de produtos
                pipeline_vendas = [
                    {"$lookup": {
                        "from": "itens_venda",
                        "localField": "_id",
                        "foreignField": "produto_id",
                        "as": "itens_venda"
                    }},
                    {"$project": {
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
                    }},
                    {"$sort": {"vendidos": -1}}
                ]
                
                produtos_data = list(produtos_col.aggregate(pipeline_vendas))
                
                # Exibe métricas
                col_p1, col_p2, col_p3, col_p4 = st.columns(4)
                with col_p1:
                    st.metric("Produtos Ativos", produtos_col.count_documents({"ativo": True}))
                with col_p2:
                    st.metric("Total em Estoque", estoque_data["total_estoque"])
                with col_p3:
                    st.metric("Valor do Estoque", f"R$ {estoque_data['valor_estoque']:,.2f}")
                with col_p4:
                    st.metric("Custo do Estoque", f"R$ {estoque_data['custo_estoque']:,.2f}")
                
                # 2. Análise por Categoria
                st.subheader("📊 Análise por Categoria")
                
                if produtos_data:
                    df_produtos = pd.DataFrame(produtos_data)
                    
                    categoria_analise = df_produtos.groupby('categoria').agg({
                        'nome': 'count',
                        'vendidos': 'sum',
                        'faturamento': 'sum',
                        'lucro': 'sum'
                    }).rename(columns={
                        'nome': 'Quantidade',
                        'vendidos': 'Unidades Vendidas',
                        'faturamento': 'Faturamento',
                        'lucro': 'Lucro'
                    })
                    
                    categoria_analise['Margem'] = (categoria_analise['Lucro'] / categoria_analise['Faturamento']) * 100
                    
                    st.dataframe(
                        categoria_analise,
                        column_config={
                            "Faturamento": st.column_config.NumberColumn(format="R$ %.2f"),
                            "Lucro": st.column_config.NumberColumn(format="R$ %.2f"),
                            "Margem": st.column_config.NumberColumn(format="%.1f%%")
                        },
                        use_container_width=True
                    )
                    
                    # 3. Top Produtos
                    st.subheader("🏆 Top Produtos")
                    
                    top_col1, top_col2 = st.columns(2)
                    
                    with top_col1:
                        st.markdown("**Mais Vendidos (Quantidade)**")
                        top_vendidos = df_produtos.sort_values('vendidos', ascending=False).head(5)
                        st.dataframe(
                            top_vendidos[['nome', 'categoria', 'vendidos']],
                            column_config={
                                "vendidos": "Unidades Vendidas"
                            },
                            hide_index=True
                        )
                    
                    with top_col2:
                        st.markdown("**Maior Faturamento**")
                        top_faturamento = df_produtos.sort_values('faturamento', ascending=False).head(5)
                        st.dataframe(
                            top_faturamento[['nome', 'categoria', 'faturamento']],
                            column_config={
                                "faturamento": st.column_config.NumberColumn(format="R$ %.2f")
                            },
                            hide_index=True
                        )
                    
                    # 4. Produtos em Risco
                    st.subheader("⚠️ Produtos em Risco")
                    
                    risco_col1, risco_col2 = st.columns(2)
                    
                    with risco_col1:
                        st.markdown("**Estoque Baixo (<10 unidades)**")
                        estoque_baixo = df_produtos[df_produtos['estoque'] < 10].sort_values('estoque')
                        if not estoque_baixo.empty:
                            st.dataframe(
                                estoque_baixo[['nome', 'categoria', 'estoque']],
                                hide_index=True
                            )
                        else:
                            st.success("Nenhum produto com estoque baixo!")
                    
                    with risco_col2:
                        st.markdown("**Sem Vendas Recentes**")
                        produtos_sem_vendas = df_produtos[df_produtos['vendidos'] == 0]
                        if not produtos_sem_vendas.empty:
                            st.dataframe(
                                produtos_sem_vendas[['nome', 'categoria', 'estoque']],
                                hide_index=True
                            )
                        else:
                            st.success("Todos os produtos tiveram vendas!")
                    
                else:
                    st.info("Nenhum dado disponível sobre produtos.")
                
            except Exception as e:
                st.error(f"Erro ao gerar relatório: {str(e)}")

    with tab3:
        st.subheader("Análise de Clientes")
        
        # Filtros para clientes
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            data_inicio_clientes = st.date_input(
                "Data Início",
                value=datetime.now() - timedelta(days=90),
                key="clientes_inicio"
            )
        with col_c2:
            data_fim_clientes = st.date_input(
                "Data Fim",
                value=datetime.now(),
                key="clientes_fim"
            )
        
        if st.button("Atualizar Relatório de Clientes", key="btn_atualizar_clientes"):
            try:
                # Filtro de período
                filtro_periodo_clientes = {
                    "data_venda": {
                        "$gte": datetime.combine(data_inicio_clientes, datetime.min.time()),
                        "$lte": datetime.combine(data_fim_clientes, datetime.max.time())
                    },
                    "status": "concluída"
                }
                
                # 1. Métricas de Clientes
                st.subheader("👥 Métricas de Clientes")
                
                # Consultas principais
                total_clientes = clientes_col.count_documents({})
                clientes_ativos = clientes_col.count_documents({"status": "ativo"})
                
                pipeline_clientes = [
                    {"$lookup": {
                        "from": "vendas",
                        "localField": "_id",
                        "foreignField": "cliente_id",
                        "as": "vendas"
                    }},
                    {"$project": {
                        "nome": 1,
                        "tipo": 1,
                        "status": 1,
                        "total_compras": {"$size": "$vendas"},
                        "total_gasto": {"$sum": "$vendas.valor_total"},
                        "ultima_compra": {"$max": "$vendas.data_venda"}
                    }},
                    {"$sort": {"total_gasto": -1}}
                ]
                
                clientes_data = list(clientes_col.aggregate(pipeline_clientes))
                
                # Exibe métricas
                col_c1, col_c2, col_c3, col_c4 = st.columns(4)
                with col_c1:
                    st.metric("Total de Clientes", total_clientes)
                with col_c2:
                    st.metric("Clientes Ativos", clientes_ativos)
                with col_c3:
                    clientes_compraram = len([c for c in clientes_data if c["total_compras"] > 0])
                    st.metric("Clientes que Compraram", clientes_compraram)
                with col_c4:
                    st.metric("Taxa de Retenção", f"{(clientes_compraram/clientes_ativos*100 if clientes_ativos > 0 else 0):.1f}%")
                
                # 2. Segmentação de Clientes
                st.subheader("📊 Segmentação de Clientes")
                
                if clientes_data:
                    df_clientes = pd.DataFrame(clientes_data)
                    
                    # Análise por tipo
                    tipo_analise = df_clientes.groupby('tipo').agg({
                        'nome': 'count',
                        'total_compras': 'sum',
                        'total_gasto': 'sum'
                    }).rename(columns={
                        'nome': 'Quantidade',
                        'total_compras': 'Compras',
                        'total_gasto': 'Faturamento'
                    })
                    
                    tipo_analise['Ticket Médio'] = tipo_analise['Faturamento'] / tipo_analise['Compras']
                    
                    st.dataframe(
                        tipo_analise,
                        column_config={
                            "Faturamento": st.column_config.NumberColumn(format="R$ %.2f"),
                            "Ticket Médio": st.column_config.NumberColumn(format="R$ %.2f")
                        },
                        use_container_width=True
                    )
                    
                    # 3. Clientes VIP
                    st.subheader("🏆 Clientes VIP (Top 10)")
                    
                    clientes_vip = df_clientes[df_clientes['total_compras'] > 0].sort_values('total_gasto', ascending=False).head(10)
                    
                    if not clientes_vip.empty:
                        st.dataframe(
                            clientes_vip[['nome', 'tipo', 'total_compras', 'total_gasto']],
                            column_config={
                                "total_compras": "Compras",
                                "total_gasto": st.column_config.NumberColumn("Faturamento", format="R$ %.2f")
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                    else:
                        st.info("Nenhum cliente com compras no período.")
                    
                    # 4. Clientes Inativos
                    st.subheader("💤 Clientes Inativos (Sem compras nos últimos 90 dias)")
                    
                    limite_inatividade = datetime.now() - timedelta(days=90)
                    clientes_inativos = df_clientes[
                        (df_clientes['ultima_compra'].isna()) | 
                        (df_clientes['ultima_compra'] < limite_inatividade)
                    ]
                    
                    if not clientes_inativos.empty:
                        st.dataframe(
                            clientes_inativos[['nome', 'tipo', 'ultima_compra']],
                            column_config={
                                "ultima_compra": st.column_config.DatetimeColumn("Última Compra", format="DD/MM/YYYY")
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                    else:
                        st.success("Todos os clientes fizeram compras recentemente!")
                    
                else:
                    st.info("Nenhum dado disponível sobre clientes.")
                
            except Exception as e:
                st.error(f"Erro ao gerar relatório: {str(e)}")

# =============================================
# FUNÇÃO PRINCIPAL
# =============================================

def main():
    st.set_page_config(
        page_title="Sari Dulces iGEST",
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
        st.title("🛒 Sari Dulces iGEST")
        st.markdown(f"**Usuário:** {st.session_state.usuario_atual['nome']}")
        st.markdown(f"**Nível:** {st.session_state.usuario_atual['nivel_acesso'].capitalize()}")
        st.markdown("---")
        
        opcoes_menu = ["👥 Clientes", "📦 Produtos", "💰 Vendas", "🚚 Entregas", "📊 Relatórios"]
        
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
    elif menu == "🚚 Entregas":
        modulo_entregas(db)
    elif menu == "📊 Relatórios":
        modulo_relatorios(db)
    elif menu == "👨‍💼 Usuários":
        modulo_usuarios(db)

if __name__ == "__main__":
    main()