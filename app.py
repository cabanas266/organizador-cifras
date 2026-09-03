import streamlit as st
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client

# Configuração da página para celular e desktop
st.set_page_config(page_title="Gerenciador de Cifras", page_icon="🎸", layout="centered")

# Credenciais do Supabase
SUPABASE_URL = "https://vnnbpjsdofrebeeycmuh.supabase.co"
SUPABASE_KEY = "sb_publishable_lSKB7eqGkItfN2s9N7PUCQ_qT9KsoEl"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# Controle de Sessão de Usuário no Streamlit
if "user" not in st.session_state:
    st.session_state.user = None

# ---------------------------------------------------------
# TELA DE LOGIN / CADASTRO
# ---------------------------------------------------------
if st.session_state.user is None:
    st.title("🎸 Gerenciador de Cifras")
    st.markdown("Faça login ou cadastre-se para acessar seu repertório seguro na nuvem.")
    
    aba_login, aba_cadastro = st.tabs(["Entrar", "Criar Conta"])
    
    with aba_login:
        email_login = st.text_input("E-mail", key="email_login")
        senha_login = st.text_input("Senha", type="password", key="senha_login")
        
        if st.button("Entrar", type="primary"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email_login, "password": senha_login})
                st.session_state.user = res.user
                st.success("Login realizado com sucesso!")
                st.rerun()
            except Exception as e:
                st.error("Erro ao entrar: Verifique seu e-mail e senha.")
                
    with aba_cadastro:
        email_cad = st.text_input("E-mail para cadastro", key="email_cad")
        senha_cad = st.text_input("Senha (mínimo 6 caracteres)", type="password", key="senha_cad")
        
        if st.button("Cadastrar Nova Conta"):
            try:
                res = supabase.auth.sign_up({"email": email_cad, "password": senha_cad})
                st.success("Conta criada com sucesso! Faça login na aba ao lado.")
            except Exception as e:
                st.error(f"Erro ao cadastrar: {e}")

else:
    # ---------------------------------------------------------
    # APLICATIVO PRINCIPAL (Usuário Logado)
    # ---------------------------------------------------------
    user = st.session_state.user
    
    col_info, col_sair = st.columns([4, 1])
    with col_info:
        st.caption(f"Conectado como: {user.email}")
    with col_sair:
        if st.button("Sair"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()

    st.title("🎸 Meu Repertório de Cifras")

    # Função para buscar músicas do usuário logado no Supabase
    def get_songs():
        try:
            response = supabase.table("songs").select("*").eq("user_id", user.id).order("title").execute()
            return response.data
        except Exception as e:
            st.error(f"Erro ao carregar músicas: {e}")
            return []

    songs = get_songs()

    # Descobrir pastas existentes a partir das músicas cadastradas
    pastas_existentes = sorted(list(set([s.get("folder", "Geral") for s in songs if s.get("folder")])))
    if not pastas_existentes:
        pastas_existentes = ["Geral"]

    # Navegação por Abas Superiores
    menu = st.radio("Navegação", ["Repertório", "Adicionar / Importar", "Pastas / Repertórios"], horizontal=True)

    if menu == "Repertório":
        st.subheader("🎵 Músicas Cadastradas")
        
        if not songs:
            st.info("Nenhuma cifra cadastrada ainda. Vá na aba 'Adicionar / Importar' para começar!")
        else:
            # Filtro por pasta
            opcoes_filtro = ["Todas"] + pastas_existentes
            filtro_pasta = st.selectbox("Filtrar por Pasta:", opcoes_filtro)
            
            musicas_filtradas = songs if filtro_pasta == "Todas" else [s for s in songs if s.get("folder") == filtro_pasta]
            
            if not musicas_filtradas:
                st.info(f"Nenhuma música encontrada na pasta '{filtro_pasta}'.")
            
            for song in musicas_filtradas:
                with st.expander(f"{song['title']} — *{song.get('artist', 'Desconhecido')}* ({song.get('folder', 'Geral')})"):
                    st.text(song.get("content", ""))
                    
                    col_del, _ = st.columns([1, 1])
                    with col_del:
                        if st.button("Excluir", key=f"del_{song['id']}"):
                            try:
                                supabase.table("songs").delete().eq("id", song["id"]).eq("user_id", user.id).execute()
                                st.success("Música excluída!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao excluir: {e}")

    elif menu == "Adicionar / Importar":
        st.subheader("🌐 Importar do Cifra Club ou Adicionar Manual")
        
        # Seção de Importação do Cifra Club
        st.markdown("### Importação Automática")
        url_cifra = st.text_input("Cole o link da cifra do Cifra Club:")
        
        # Seleção ou criação de pasta na importação
        modo_pasta_imp = st.radio("Destino da Pasta", ["Selecionar existente", "Criar nova pasta"], key="modo_imp")
        if modo_pasta_imp == "Selecionar existente":
            pasta_import = st.selectbox("Pasta:", pastas_existentes, key="sel_pasta_imp")
        else:
            pasta_import = st.text_input("Nome da nova pasta:", value="Geral", key="nova_pasta_imp")
        
        if st.button("Importar Cifra"):
            if not url_cifra:
                st.warning("Por favor, insira um link válido.")
            else:
                try:
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                    resposta = requests.get(url_cifra, headers=headers)
                    
                    if resposta.status_code == 200:
                        soup = BeautifulSoup(resposta.text, "html.parser")
                        
                        titulo_tag = soup.find("h1")
                        artista_tag = soup.find("h2")
                        cifra_tag = soup.find("pre")
                        
                        titulo = titulo_tag.text.strip() if titulo_tag else "Sem Título"
                        artista = artista_tag.text.strip() if artista_tag else "Desconhecido"
                        conteudo = cifra_tag.text if cifra_tag else "Não foi possível extrair o texto automaticamente."
                        
                        pasta_final = pasta_import.strip() if pasta_import else "Geral"
                        
                        novo_dado = {
                            "title": titulo,
                            "artist": artista,
                            "folder": pasta_final,
                            "content": conteudo,
                            "user_id": user.id
                        }
                        supabase.table("songs").insert(novo_dado).execute()
                        st.success(f"Cifra '{titulo}' importada com sucesso para a pasta '{pasta_final}'!")
                        st.rerun()
                    else:
                        st.error("Não foi possível acessar a página informada. Verifique o link.")
                except Exception as e:
                    st.error(f"Erro ao importar: {e}")

        st.markdown("---")
        st.markdown("### Cadastro Manual")
        with st.form("form_add_manual"):
            titulo_m = st.text_input("Título da Música *")
            artista_m = st.text_input("Artista / Banda")
            
            # Opção de pasta no cadastro manual
            pasta_m = st.selectbox("Pasta / Repertório", pastas_existentes, key="sel_pasta_man")
            
            conteudo_m = st.text_area("Cifra e Letra", height=200, placeholder="Cole a cifra aqui...")
            
            salvar_m = st.form_submit_button("Salvar na Nuvem")
            
            if salvar_m:
                if not titulo_m:
                    st.warning("O título é obrigatório!")
                else:
                    try:
                        novo_dado = {
                            "title": titulo_m,
                            "artist": artista_m,
                            "folder": pasta_m,
                            "content": conteudo_m,
                            "user_id": user.id
                        }
                        supabase.table("songs").insert(novo_dado).execute()
                        st.success(f"Cifra salva com sucesso na pasta '{pasta_m}'!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

    elif menu == "Pastas / Repertórios":
        st.subheader("📁 Gerenciamento de Pastas")
        if not songs:
            st.info("Cadastre algumas músicas para ver suas pastas aqui.")
        else:
            for p in pastas_existentes:
                qtd = len([s for s in songs if s.get("folder") == p])
                with st.expander(f"📁 {p} ({qtd} música(s))"):
                    musicas_da_pasta = [s for s in songs if s.get("folder") == p]
                    if musicas_da_pasta:
                        for m in musicas_da_pasta:
                            st.write(f"- **{m['title']}** — *{m.get('artist', 'Desconhecido')}*")
                    else:
                        st.write("Nenhuma música nesta pasta.")
