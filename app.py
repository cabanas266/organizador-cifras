import streamlit as st
from supabase import create_client, Client

# Configuração da página para celular e desktop
st.set_page_config(page_title="Gerenciador de Cifras", page_icon="🎸", layout="centered")

# Credenciais do Supabase fornecidas
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
# TELA DE LOGIN / CADASTRO (Isolamento de Dados por Usuário)
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
                st.error(f"Erro ao entrar: Verifique seu e-mail e senha.")
                
    with aba_cadastro:
        email_cad = st.text_input("E-mail para cadastro", key="email_cad")
        senha_cad = st.text_input("Senha (mínimo 6 caracteres)", type="password", key="senha_cad")
        
        if st.button("Cadastrar Nova Conta"):
            try:
                res = supabase.auth.sign_up({"email": email_cad, "password": senha_cad})
                st.success("Conta criada com sucesso! Verifique seu e-mail se necessário ou faça login na aba ao lado.")
            except Exception as e:
                st.error(f"Erro ao cadastrar: {e}")

else:
    # ---------------------------------------------------------
    # APLICATIVO PRINCIPAL (Usuário Logado)
    # ---------------------------------------------------------
    user = st.session_state.user
    
    # Barra superior com informações e botão de saída
    col_info, col_sair = st.columns([4, 1])
    with col_info:
        st.caption(f"Conectado como: {user.email}")
    with col_sair:
        if st.button("Sair"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()

    st.title("🎸 Meu Repertório de Cifras")

    # Navegação por Abas Superiores (Otimizado para Mobile)
    menu = st.radio("Navegação", ["Repertório", "Adicionar / Editar", "Pastas / Repertórios"], horizontal=True)

    # Função auxiliar para buscar músicas do usuário logado
    def get_songs():
        try:
            response = supabase.table("songs").select("*").eq("user_id", user.id).execute()
            return response.data
        except Exception as e:
            st.error(f"Erro ao carregar músicas: {e}")
            return []

    songs = get_songs()

    if menu == "Repertório":
        st.subheader("🎵 Músicas Cadastradas")
        
        if not songs:
            st.info("Nenhuma cifra cadastrada ainda. Vá na aba 'Adicionar / Editar' para começar!")
        else:
            # Filtro por pasta/repertório
            pastas_disponiveis = ["Todas"] + list(set([s.get("folder", "Geral") for s in songs if s.get("folder")]))
            filtro_pasta = st.selectbox("Filtrar por Pasta:", pastas_disponiveis)
            
            musicas_filtradas = songs if filtro_pasta == "Todas" else [s for s in songs if s.get("folder") == filtro_pasta]
            
            for song in musicas_filtradas:
                with st.expander(f"{song['title']} — *{song.get('artist', 'Desconhecido')}* ({song.get('folder', 'Geral')})"):
                    st.text(song.get("content", ""))
                    
                    col_del, col_edit = st.columns([1, 1])
                    with col_del:
                        if st.button("Excluir", key=f"del_{song['id']}"):
                            try:
                                supabase.table("songs").delete().eq("id", song["id"]).eq("user_id", user.id).execute()
                                st.success("Música excluída!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao excluir: {e}")

    elif menu == "Adicionar / Editar":
        st.subheader("➕ Adicionar Nova Cifra")
        
        with st.form("form_add_song"):
            titulo = st.text_input("Título da Música *")
            artista = st.text_input("Artista / Banda")
            pasta = st.text_input("Pasta / Repertório (Ex: Show Acústico, Ensaio)", value="Geral")
            conteudo = st.text_area("Cifra e Letra", height=250, placeholder="Cole a cifra aqui com os acordes alinhados...")
            
            salvar = st.form_submit_button("Salvar Cifra na Nuvem")
            
            if salvar:
                if not titulo:
                    st.warning("O título da música é obrigatório!")
                else:
                    try:
                        novo_dado = {
                            "title": titulo,
                            "artist": artista,
                            "folder": pasta,
                            "content": conteudo,
                            "user_id": user.id
                        }
                        supabase.table("songs").insert(novo_dado).execute()
                        st.success("Cifra salva com sucesso na nuvem!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

    elif menu == "Pastas / Repertórios":
        st.subheader("📁 Organização de Pastas")
        if not songs:
            st.info("Cadastre algumas músicas para ver suas pastas aqui.")
        else:
            pastas = set([s.get("folder", "Geral") for s in songs])
            for p in pastas:
                qtd = len([s for s in songs if s.get("folder") == p])
                st.write(f"📁 **{p}** — {qtd} música(s)")
