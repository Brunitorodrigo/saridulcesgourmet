# delivery_module.py
import datetime
from bson.objectid import ObjectId
from pymongo.errors import PyMongoError
import streamlit as st # Para exibir mensagens de erro/sucesso

# Nome da coleção no MongoDB
COLLECTION_NAME = "entregas"

def _get_collection(db):
    """Helper para obter a coleção MongoDB 'entregas'."""
    if db is None:
        st.error("Erro crítico: Conexão com o banco de dados não disponível para o módulo de entregas.")
        return None
    try:
        return db[COLLECTION_NAME]
    except Exception as e:
        st.error(f"Erro ao acessar a coleção '{COLLECTION_NAME}': {e}")
        return None

def _parse_date(date_input):
    """Valida e converte a data para datetime.datetime (necessário para MongoDB)."""
    if isinstance(date_input, datetime.datetime):
        return date_input # Já está no formato correto
    if isinstance(date_input, datetime.date):
        # Converte date para datetime (meia-noite)
        return datetime.datetime.combine(date_input, datetime.datetime.min.time())
    try:
        # Tenta converter de string AAAA-MM-DD
        return datetime.datetime.strptime(str(date_input), '%Y-%m-%d')
    except ValueError:
        # Tenta converter de string DD/MM/YYYY
        try:
            return datetime.datetime.strptime(str(date_input), '%d/%m/%Y')
        except ValueError:
            raise ValueError("Formato de data inválido. Use AAAA-MM-DD ou DD/MM/YYYY.")

def _validate_type(type_input):
    """Valida o tipo de entrega e retorna o valor interno ('pickup' ou 'delivery')."""
    # Mapeia os textos da interface para valores internos consistentes
    valid_types_map = {
        'retirada na loja': 'pickup',
        'envio ao cliente': 'delivery'
    }
    type_lower = str(type_input).lower().strip()
    internal_type = valid_types_map.get(type_lower)

    if not internal_type:
        # Permite também os tipos internos como válidos (caso já venham assim)
        if type_lower in ['pickup', 'delivery']:
            internal_type = type_lower
        else:
            # Usa as opções da interface na mensagem de erro
            raise ValueError(f"Tipo de entrega inválido ('{type_input}'). Use 'Retirada na Loja' ou 'Envio ao Cliente'.")
    return internal_type

def add_or_update_delivery(db, venda_id, delivery_date, delivery_type, cost=0.0):
    """
    Adiciona uma nova entrega ou ATUALIZA uma existente para a venda_id fornecida.
    Garante que cada venda tenha no máximo uma entrada de entrega.
    """
    collection = _get_collection(db)
    if not collection: return None

    try:
        venda_object_id = ObjectId(venda_id) # Garante que é um ObjectId válido
        parsed_date = _parse_date(delivery_date)
        internal_type = _validate_type(delivery_type)
        delivery_cost = float(cost) if cost is not None else 0.0
        now = datetime.datetime.now()

        # Procura por entrega existente para esta venda
        existing = collection.find_one({"venda_id": venda_object_id})

        update_data = {
            "delivery_date": parsed_date,
            "delivery_type": internal_type,
            "cost": delivery_cost,
            "last_updated": now
        }

        if existing:
            # Atualiza a entrega existente
            result = collection.update_one(
                {"_id": existing['_id']},
                {"$set": update_data}
            )
            if result.modified_count > 0:
                st.success(f"Informações de entrega para venda {venda_id} atualizadas.")
                # Retorna o documento atualizado buscando pelo _id original
                return find_delivery_by_id(db, existing['_id'])
            else:
                # st.info(f"Nenhuma alteração nos dados de entrega para venda {venda_id}.")
                return existing # Retorna o documento existente sem alterações
        else:
            # Insere uma nova entrega
            delivery_doc = {
                "venda_id": venda_object_id,
                "created_at": now,
                **update_data # Adiciona os campos do update_data
            }
            result = collection.insert_one(delivery_doc)
            st.success(f"Informações de entrega adicionadas para venda {venda_id} (ID Entrega: {result.inserted_id}).")
            # Retorna o documento inserido buscando pelo novo ID
            return find_delivery_by_id(db, result.inserted_id)

    except (ValueError, PyMongoError) as e:
        st.error(f"Erro ao salvar informações de entrega para venda {venda_id}: {e}")
        return None
    except Exception as e: # Captura erros de ObjectId inválido, etc.
         st.error(f"Erro inesperado ao processar entrega para venda {venda_id}: {e}")
         return None

def find_delivery_by_id(db, delivery_id):
    """Encontra uma entrega pelo seu ObjectId."""
    collection = _get_collection(db)
    if not collection: return None
    try:
        return collection.find_one({"_id": ObjectId(delivery_id)})
    except PyMongoError as e:
        st.error(f"Erro ao buscar entrega por ID {delivery_id}: {e}")
        return None
    except Exception as e: # Captura ObjectId inválido
        st.warning(f"Formato de ID de entrega inválido: {delivery_id}. Erro: {e}")
        return None

def find_delivery_by_venda_id(db, venda_id):
    """Encontra a entrega associada a um ObjectId de venda."""
    collection = _get_collection(db)
    if not collection: return None
    try:
        # Assume uma entrega por venda.
        return collection.find_one({"venda_id": ObjectId(venda_id)})
    except PyMongoError as e:
        st.error(f"Erro ao buscar entrega por ID da venda {venda_id}: {e}")
        return None
    except Exception as e: # Captura ObjectId inválido
        st.warning(f"Formato de ID de venda inválido: {venda_id}. Erro: {e}")
        return None

def edit_delivery(db, delivery_id, new_date=None, new_type=None, new_cost=None):
    """Edita campos específicos de uma entrega existente no MongoDB."""
    collection = _get_collection(db)
    if not collection: return False

    update_fields = {"last_updated": datetime.datetime.now()}
    try:
        # Valida e prepara campos para atualização apenas se foram fornecidos
        if new_date is not None:
            update_fields["delivery_date"] = _parse_date(new_date)
        if new_type is not None:
            update_fields["delivery_type"] = _validate_type(new_type)
        if new_cost is not None: # Permite definir custo como 0.0
            update_fields["cost"] = float(new_cost)

        # Verifica se há algo para atualizar além da data de modificação
        if len(update_fields) == 1:
            st.info("Nenhuma alteração fornecida para a entrega.")
            return False

        result = collection.update_one(
            {"_id": ObjectId(delivery_id)},
            {"$set": update_fields}
        )

        if result.matched_count == 0:
            st.error(f"Erro: Entrega com ID {delivery_id} não encontrada para edição.")
            return False
        if result.modified_count > 0:
            st.success(f"Entrega ID {delivery_id} atualizada com sucesso.")
            return True
        else:
            st.info(f"Nenhuma alteração detectada nos dados da entrega ID {delivery_id}.")
            return False # Encontrou mas nenhum valor foi realmente diferente

    except (ValueError, PyMongoError) as e:
        st.error(f"Erro ao editar entrega ID {delivery_id}: {e}")
        return False
    except Exception as e: # Captura ObjectId inválido
        st.error(f"Formato de ID de entrega inválido: {delivery_id}. Erro: {e}")
        return False

def get_deliveries(db, start_date=None, end_date=None, venda_id_filter=None, delivery_type_filter=None):
    """Busca entregas no MongoDB, com filtros e ordenação por data."""
    collection = _get_collection(db)
    if not collection: return []

    query = {}
    try:
        # Filtro por Data
        date_query = {}
        if start_date:
            date_query["$gte"] = _parse_date(start_date)
        if end_date:
            # Ajusta end_date para incluir o dia inteiro até 23:59:59
            end_dt = _parse_date(end_date).replace(hour=23, minute=59, second=59, microsecond=999999)
            date_query["$lte"] = end_dt
        if date_query:
            query["delivery_date"] = date_query

        # Filtro por ID da Venda
        if venda_id_filter:
            try:
                query["venda_id"] = ObjectId(venda_id_filter)
            except Exception:
                st.warning(f"ID de Venda inválido para filtro: '{venda_id_filter}'. Ignorando este filtro.")

        # Filtro por Tipo de Entrega
        if delivery_type_filter and delivery_type_filter.lower() != 'todos':
             try:
                 internal_type = _validate_type(delivery_type_filter)
                 query["delivery_type"] = internal_type
             except ValueError:
                  st.warning(f"Tipo de entrega inválido para filtro: '{delivery_type_filter}'. Ignorando este filtro.")

        # Busca e ordena por data de entrega (mais antiga primeiro)
        deliveries = list(collection.find(query).sort("delivery_date", 1))
        return deliveries

    except (ValueError, PyMongoError) as e:
        st.error(f"Erro ao buscar calendário de entregas: {e}")
        return []
    except Exception as e:
         st.error(f"Erro inesperado ao buscar entregas: {e}")
         return []

def format_delivery_details(delivery_doc):
    """Formata um documento de entrega MongoDB para exibição amigável."""
    if not delivery_doc or not isinstance(delivery_doc, dict):
        return "N/D" # Não disponível ou formato inválido

    delivery_id = delivery_doc.get('_id', 'N/A')
    venda_id = delivery_doc.get('venda_id', 'N/A')
    date_obj = delivery_doc.get('delivery_date')
    delivery_type = delivery_doc.get('delivery_type', 'N/A') # 'pickup' ou 'delivery'
    cost = delivery_doc.get('cost', 0.0)

    # Formatação da Data
    data_str = date_obj.strftime('%d/%m/%Y') if isinstance(date_obj, datetime.datetime) else "Data Inválida"

    # Formatação do Tipo
    if delivery_type == 'pickup':
        tipo_str = "Retirada"
    elif delivery_type == 'delivery':
        tipo_str = "Envio"
    else:
        tipo_str = "Tipo N/D"

    # Formatação do Custo
    custo_str = f"R$ {cost:.2f}" if cost > 0 else "Grátis"

    # Retorna string formatada (pode ajustar conforme preferir)
    return f"📅 {data_str} | 🚚 {tipo_str} ({custo_str})"
    # Alternativa mais detalhada:
    # return f"**Data:** {data_str} | **Tipo:** {tipo_str} | **Custo:** {custo_str} (Entrega ID: {delivery_id})"

def get_delivery_cost(db, venda_id):
    """Retorna o custo de entrega registrado para uma venda específica."""
    delivery = find_delivery_by_venda_id(db, venda_id)
    if delivery and isinstance(delivery, dict):
        return delivery.get('cost', 0.0)
    else:
        # Se não encontrar info, assume custo 0.
        # Isso pode ocorrer se a venda for antiga ou se for uma retirada sem custo registrado explicitamente.
        return 0.0