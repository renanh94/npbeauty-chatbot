
import random
import time

from app.database.manipulations import ia_manipulations, lead_manipulations
from app.service.queue_manager import get_phone_lock
from app.service.llm_response import IAresponse
from app.service.quebra_mensagens import *

def process_webhook_data(data:dict):
    """
    Função par processar todos os dados do nosso webhook
    """

    try:
        #Coletar infos basica 
        ia_phone = data["sender"].split("@")[0]
        ia_name = data["instance"]

        # Pesquisar em nosso database qual IA direcionar
        ia_infos = ia_manipulations.filter_ia(ia_phone)
        if not ia_infos:
            raise(Exception("IA Não localizada com esse telefone em nosso DB"))
        
        if ia_infos.status != True:
            raise(Exception(f"IA {ia_infos.nome} Esta Desativada, interceptando mensagem"))
        
        # Extrair conteudo da mensagem
        mensage_id = data["data"]["key"]["id"]
        mensage_type = data["data"]["messageType"]
        message_content = processar_menssagem(data, ia_name, mensage_id, mensage_type, ia_infos)
        if not message_content:
            raise(Exception(f"Tipo de mensagem não foi possivel processar : {mensage_type}"))
        
        # extraindo informações do lead
        lead_name = data["data"]["pushName"]
        lead_phone = data["data"]["key"]["remoteJid"].split("@")[0]

        lock = get_phone_lock(lead_phone)
        with lock:
            message_atual_lead = {
                "role":"user",
                "name": lead_name,
                "content": message_content
            }
            lead_db = lead_manipulations.filter_lead(lead_phone, message_atual_lead)
            if not lead_db:
                lead_db = lead_manipulations.new_lead(ia_infos.id, lead_name, lead_phone, [message_atual_lead])
            
            #Gerando resposta com LLM
            historico = lead_db.message
            resume_lead = lead_db.resume
            api_key = ia_infos.ia_config.credentials.get("api_key")
            ia_model = ia_infos.ia_config.credentials.get("ai_model", "")
            system_prompt = ia_infos.active_prompt
            if not system_prompt:
                raise(Exception("Nenhum prompt cadastrado ou ativo para a ia"))

            llm = IAresponse(api_key, ia_model, system_prompt.prompt_text, resume_lead)
            response_lead = llm.generate_response(message_content, historico)
            if not response_lead:
                raise(Exception("Nenhuma resposta foi gerada pela ia"))
            
            # Tratar mensagem da IA
            list_message_to_lead = quebrar_mensagens(response_lead)
            if not list_message_to_lead:
                list_message_to_lead = [response_lead]
            
            # Envio messagem para o lead
            for msg in list_message_to_lead:
                delay = calculate_typing_delay(msg)
                print(f"Delay : {delay}s")
                print(f"IA: {msg}")

            # Verificar quantidade de interações
            resumo = None
            total_interacoes = 0
            ultimo_role = None
            for mensagem in historico:
                if mensagem["role"] != ultimo_role:
                    total_interacoes +=1
                    ultimo_role = mensagem["role"]

            print(f"Total de interações reais {total_interacoes}")

            for n in range(2, 15):
                print(n)
                if total_interacoes % n == 0:
                    print(f"Interações bateu {total_interacoes} criando resumo")
                    resumo = llm.generate_resume(historico)
                    break

            # Ataulizando no banco de dados
            message_ia = {
                "role":"assistant",
                "content": response_lead
            }
            lead_update = lead_manipulations.update_lead(lead_db.id, message_ia, resumo)
            if not lead_update:
                raise(Exception(f"Ocorreu um problema ao atualizar o lead : {lead_db.id}"))
            
            print(f"SUCESSO AO PROCESSAR LEAD {lead_db.name}")


    except Exception as ex:
        print(f"ERROR IN PROCESS: {ex}")

def processar_menssagem(data:dict, instance:str, message_id:str, message_type:str, ia_infos: object) -> str:
    if message_type == "conversation":
        return data["data"]["message"]["conversation"]
    
    elif message_type == "extendedTextMessage":
        return data["data"]["message"]["extendedTextMessage"]["text"]
    
    elif message_type == "imageMessage":
        print("Imagem detectada!")
        #return processar_imagem(instance, message_id, ia_infos)
        return "mensagem de imagem"
    
    elif message_type == "audioMessage":
        print("Áudio identificado!")
        #return processar_audio(instance, message_id, ia_infos)
        return "mensagem de audio"
    
    elif message_type == "documentWithCaptionMessage":
        print("Documento identificado!")
        type_file = data.get("data").get("message").get("documentWithCaptionMessage").get("message").get("documentMessage").get("mimetype").split("/")[1]
        #return processar_documento(instance, message_id, type_file, ia_infos), type_file
        return "mensagem de documento"
    else:
        print(f"Tipo de mensagem não identificada: {message_type} retornando...")
        return ""