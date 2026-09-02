import sqlite3
import streamlit as st
import requests
from bs4 import BeautifulSoup
import re

st.set_page_config(page_title="Organizador de Cifras & Repertório", page_icon="🎸", layout="centered")

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect("cifras_control.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT NOT NULL,
            original_tone TEXT,
            current_tone TEXT,
            content TEXT,
            folder_id INTEGER,
            FOREIGN KEY (folder_id) REFERENCES folders (id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect("cifras_control.db")

# --- ESCALA MUSICAL PARA TRANSPOSIÇÃO ---
NOTES_SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
FLAT_TO_SHARP = {'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'}

def normalize_note(note):
    note = note.strip()
    if note in FLAT_TO_SHARP:
        return FLAT_TO_SHARP[note]
    return note

def transpose_chord(chord, semitones):
    match = re.match(r'^([A-G][b#]?)', chord)
    if not match:
        return chord
    
    root = match.group(1)
    norm_root = normalize_note(root)
    
    if norm_root not in NOTES_SHARP:
        return chord
    
    idx = NOTES_SHARP.index(norm_root)
    new_idx = (idx + semitones) % 12
    new_root = NOTES_SHARP[new_idx]
    
    return chord.replace(root, new_root, 1)

def transpose_content_text(content, semitones):
    if semitones == 0:
        return content
    
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        words = line.split()
        new_words = []
        is_chord_line = False
        
        if words:
            chord_count = 0
            for w in words:
                clean_w = re.sub(r'[^A-G0-9b#/#m()+-]', '', w)
                if re.match(r'^[A-G][b#]?[m°0-9sus4addmaj7/-]*$', clean_w):
                    chord_count += 1
            if chord_count >= len(words) * 0.4 or len(words) <= 3:
                is_chord_line = True
        
        if is_chord_line:
            new_line = line
            for word in words:
                m = re.match(r'^([^\w]*)([A-G][b#]?[m°0-9sus4addmaj8/-]*)([^\w]*)$', word)
                if m:
                    prefix, chord, suffix = m.groups()
                    transposed = transpose_chord(chord, semitones)
                    new_word = f"{prefix}{transposed}{suffix}"
                    new_line = new_line.replace(word, new_word, 1)
            new_lines.append(new_line)
        else:
            new_lines.append(line)
            
    return '\n'.join(new_lines)

# --- SCRAPER DO CIFRA CLUB ATUALIZADO ---
def fetch_cifraclub(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None, None, None, "Erro ao acessar o link."
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title_tag = soup.find('h1', class_='t1') or soup.find('h1', class_='cnt-head-title')
        artist_tag = soup.find('h2', class_='t3') or soup.find('h2', class_='cnt-head-sub-title')
        
        title = title_tag.text.strip() if title_tag else ""
        artist = artist_tag.text.strip() if artist_tag else ""
        
        if not title or not artist or "html" in title.lower():
            parts = [p for p in url.strip('/').split('/') if p]
            if parts and (parts[-1].endswith('.html') or parts[-1] in ['simplificada', 'baixo', 'teclado', 'ukulele']):
                parts.pop()
                
            if len(parts) >= 2:
                if not artist:
                    artist = parts[-2].replace('-', ' ').title()
                if not title or "html" in title.lower():
                    title = parts[-1].replace('-', ' ').title()
                    
        # Busca correta do tom original atualizada para o layout novo do Cifra Club
        tone_tag = soup.find(class_=re.sub(r'\s+', '', 'Cifra_tone__')) or soup.find('a', class_='js-cifra-tone')
        if not tone_tag:
            # Procura pelo texto do tom logo após a tag "Tom:"
            tone_label = soup.find(text=re.compile(r'Tom:', re.I))
            if tone_label and tone_label.find_next():
                original_tone = tone_label.find_next().text.strip()
            else:
                original_tone = "C"
        else:
            original_tone = tone_tag.text.strip()
            
        # Garante que pegou só a nota limpa (ex: "Tom: G" vira "G")
        original_tone = re.sub(r'[^A-G][b#]?', '', original_tone) or "C"
            
        pre_tag = soup.find('pre')
        if pre_tag:
            content = pre_tag.get_text()
        else:
            return None, None, None, "Não foi possível encontrar a estrutura da cifra nesta página."
            
        return title or "Desconhecido", artist or "Desconhecido", original_tone, content
    except Exception as e:
        return None, None, None, f"Erro na importação: {str(e)}"

# --- CONTROLE DE NAVEGAÇÃO POR ESTADO ---
if 'nav_menu' not in st.session_state:
    st.session_state['nav_menu'] = "Visualizar / Tocar"

if 'selected_song_to_play' not in st.session_state:
    st.session_state['selected_song_to_play'] = None

# --- MENU LATERAL ---
st.sidebar.title("🎸 Cifras & Repertório")
menu_options = ["Visualizar / Tocar", "Adicionar / Importar Cifra", "Gerenciar Pastas", "Lista Geral"]

current_index = menu_options.index(st.session_state['nav_menu']) if st.session_state['nav_menu'] in menu_options else 0
chosen_menu = st.sidebar.radio("Navegação", menu_options, index=current_index)

if chosen_menu != st.session_state['nav_menu']:
    st.session_state['nav_menu'] = chosen_menu
    st.rerun()

menu = st.session_state['nav_menu']

conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT id, name FROM folders")
folders = cursor.fetchall()
folder_dict = {f[1]: f[0] for f in folders}
conn.close()

# ----------------- ABA 1: VISUALIZAR / TOCAR -----------------
if menu == "Visualizar / Tocar":
    st.header("🎵 Palco / Ensaio")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, artist, original_tone, content, folder_id FROM songs ORDER BY title ASC")
    songs = cursor.fetchall()
    conn.close()
    
    if not songs:
        st.info("Nenhuma cifra cadastrada ainda. Vá em 'Adicionar / Importar Cifra' no menu lateral.")
    else:
        song_dict = {f"{s[1]} - {s[2]} (ID: {s[0]})": s for s in songs}
        song_names = list(song_dict.keys())
        
        default_idx = 0
        if st.session_state['selected_song_to_play']:
            for idx, name in enumerate(song_names):
                if f"ID: {st.session_state['selected_song_to_play']})" in name:
                    default_idx = idx
                    break
            st.session_state['selected_song_to_play'] = None
            
        selected_song_name = st.selectbox("Escolher Música", song_names, index=default_idx)
        
        s_id, title, artist, orig_tone, content, folder_id = song_dict[selected_song_name]
        
        folder_name = "Geral"
        for f_name, f_id in folder_dict.items():
            if f_id == folder_id:
                folder_name = f_name
                
        st.subheader(f"{title} - *{artist}*")
        st.caption(f"📂 Pasta: {folder_name} | Tom Original: **{orig_tone or 'C'}**")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("⬅️ Abaixar Semitom"):
                st.session_state[f"trans_{s_id}"] = st.session_state.get(f"trans_{s_id}", 0) - 1
        with col2:
            if st.button("Subir Semitom ➡"):
                st.session_state[f"trans_{s_id}"] = st.session_state.get(f"trans_{s_id}", 0) + 1
        with col3:
            chosen_tone = st.selectbox("Ou escolha o tom direto:", ["Original", "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"], key=f"tone_sel_{s_id}")
            
        current_trans = st.session_state.get(f"trans_{s_id}", 0)
        
        # Correção para o botão "Original" voltar perfeitamente ao tom original
        if chosen_tone == "Original":
            current_trans = 0
            st.session_state[f"trans_{s_id}"] = 0
        elif orig_tone:
            norm_orig = normalize_note(orig_tone)
            norm_chosen = normalize_note(chosen_tone)
            if norm_orig in NOTES_SHARP and norm_chosen in NOTES_SHARP:
                idx_orig = NOTES_SHARP.index(norm_orig)
                idx_chosen = NOTES_SHARP.index(norm_chosen)
                diff = idx_chosen - idx_orig
                current_trans = diff
                st.session_state[f"trans_{s_id}"] = diff

        st.markdown(f"**Transposição atual:** {current_trans:+d} semitons")
        
        transposed_content = transpose_content_text(content, current_trans)
        
        st.markdown("---")
        st.code(transposed_content, language="text")

# ----------------- ABA 2: ADICIONAR / IMPORTAR -----------------
elif menu == "Adicionar / Importar Cifra":
    st.header("📥 Adicionar Cifra")
    
    import_type = st.radio("Método de Cadastro", ["Importar do Cifra Club (Link)", "Digitar / Colar Manualmente"])
    
    folder_names = ["Nenhuma (Geral)"] + list(folder_dict.keys())
    selected_folder = st.selectbox("Salvar na Pasta / Repertório", folder_names)
    target_folder_id = folder_dict.get(selected_folder) if selected_folder != "Nenhuma (Geral)" else None
    
    if import_type == "Importar do Cifra Club (Link)":
        url_input = st.text_input("Cole o link da música do Cifra Club (ex: https://www.cifraclub.com.br/artista/musica/)")
        if st.button("Puxar Cifra da Web"):
            if url_input.strip():
                with st.spinner("Buscando dados no Cifra Club..."):
                    t, a, ot, c = fetch_cifraclub(url_input)
                    st.session_state["temp_title"] = t
                    st.session_state["temp_artist"] = a
                    st.session_state["temp_tone"] = ot
                    st.session_state["temp_content"] = c
                    st.success(f"Sucesso! Música encontrada: {t} - {a} (Tom Original: {ot})")
            else:
                st.warning("Insira um link válido.")
                
        st.markdown("---")
        song_title = st.text_input("Nome da Música", value=st.session_state.get("temp_title", ""))
        song_artist = st.text_input("Artista / Banda", value=st.session_state.get("temp_artist", ""))
        song_tone = st.text_input("Tom Original", value=st.session_state.get("temp_tone", "C"))
        song_content = st.text_area("Cifra Completa", value=st.session_state.get("temp_content", ""), height=300)
        
        if st.button("Salvar no Repertório"):
            if song_title and song_content:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO songs (title, artist, original_tone, current_tone, content, folder_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (song_title, song_artist, song_tone, song_tone, song_content, target_folder_id)
                )
                conn.commit()
                conn.close()
                st.success("Cifra salva com sucesso no banco de dados!")
            else:
                st.warning("Preencha pelo menos o título e a cifra.")

    else:
        m_title = st.text_input("Nome da Música")
        m_artist = st.text_input("Artista / Banda")
        m_tone = st.text_input("Tom Original (ex: C, Am, G)", value="C")
        m_content = st.text_area("Cole a Cifra com os acordes", height=300)
        
        if st.button("Salvar Cifra Manual"):
            if m_title and m_content:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO songs (title, artist, original_tone, current_tone, content, folder_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (m_title, m_artist, m_tone, m_tone, m_content, target_folder_id)
                )
                conn.commit()
                conn.close()
                st.success("Cifra manual salva com sucesso!")
            else:
                st.warning("Preencha o título e o conteúdo da cifra.")

# ----------------- ABA 3: GERENCIAR PASTAS -----------------
elif menu == "Gerenciar Pastas":
    st.header("📂 Gerenciar Pastas / Repertórios de Shows")
    
    new_folder_name = st.text_input("Nome da Nova Pasta (ex: Show Acústico, Reggae Night)")
    if st.button("Criar Pasta"):
        if new_folder_name.strip():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO folders (name) VALUES (?)", (new_folder_name,))
            conn.commit()
            conn.close()
            st.success(f"Pasta '{new_folder_name}' criada com sucesso!")
            st.rerun()
        else:
            st.warning("Digite um nome válido.")
            
    st.markdown("---")
    st.subheader("Pastas Existentes e Músicas Vinculadas")
    if folders:
        for f_id, f_name in folders:
            with st.expander(f"📁 {f_name}"):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id, title, artist, original_tone FROM songs WHERE folder_id = ? ORDER BY title ASC", (f_id,))
                folder_songs = cursor.fetchall()
                conn.close()
                
                if folder_songs:
                    for s_id, title, artist, tone in folder_songs:
                        col_txt, col_play, col_del = st.columns([3, 1, 1])
                        col_txt.write(f"🎵 **{title}** - *{artist}* (Tom: {tone or 'C'})")
                        if col_play.button("Tocar", key=f"play_folder_song_{s_id}"):
                            st.session_state['selected_song_to_play'] = s_id
                            st.session_state['nav_menu'] = "Visualizar / Tocar"
                            st.rerun()
                        if col_del.button("Excluir", key=f"del_folder_song_{s_id}"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM songs WHERE id = ?", (s_id,))
                            conn.commit()
                            conn.close()
                            st.success("Música excluída!")
                            st.rerun()
                else:
                    st.info("Nenhuma música nesta pasta.")
                
                if st.button("Apagar Pasta Inteira", key=f"del_folder_{f_id}"):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE songs SET folder_id = NULL WHERE folder_id = ?", (f_id,))
                    cursor.execute("DELETE FROM folders WHERE id = ?", (f_id,))
                    conn.commit()
                    conn.close()
                    st.success("Pasta removida!")
                    st.rerun()
    else:
        st.info("Nenhuma pasta criada ainda.")

# ----------------- ABA 4: LISTA GERAL -----------------
elif menu == "Lista Geral":
    st.header("📚 Lista Geral de Músicas")
    
    sort_by = st.radio("Ordenar por:", ["Ordem Alfabética de Música", "Ordem Alfabética de Artista"], horizontal=True)
    order_query = "ORDER BY title ASC" if sort_by == "Ordem Alfabética de Música" else "ORDER BY artist ASC"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT id, title, artist, original_tone, folder_id FROM songs {order_query}")
    songs = cursor.fetchall()
    conn.close()
    
    if songs:
        st.write(f"Total de músicas cadastradas: **{len(songs)}**")
        st.markdown("---")
        for s_id, title, artist, tone, folder_id in songs:
            folder_label = "Geral"
            for f_name, f_id in folder_dict.items():
                if f_id == folder_id:
                    folder_label = f_name
            
            col_info, col_play, col_del = st.columns([3, 1, 1])
            col_info.write(f"🎵 **{title}** - *{artist}* (Tom: {tone or 'C'} | 📂 {folder_label})")
            
            if col_play.button("Tocar", key=f"play_song_{s_id}"):
                st.session_state['selected_song_to_play'] = s_id
                st.session_state['nav_menu'] = "Visualizar / Tocar"
                st.rerun()
                
            if col_del.button("Excluir", key=f"del_song_{s_id}"):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM songs WHERE id = ?", (s_id,))
                conn.commit()
                conn.close()
                st.success("Música excluída!")
                st.rerun()
    else:
        st.info("Nenhuma música cadastrada no sistema.")
