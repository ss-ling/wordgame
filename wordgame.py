import streamlit as st
import pandas as pd
import sqlite3
import json
import random
import time

# --- CONSTANTS ---
BOARD_SIZE = 15
LETTER_VALUES = {
    "A": 1, "B": 3, "C": 3, "D": 2, "E": 1, "F": 4, "G": 2, "H": 4, "I": 1, 
    "J": 8, "K": 5, "L": 1, "M": 3, "N": 1, "O": 1, "P": 3, "Q": 10, "R": 1, 
    "S": 1, "T": 1, "U": 1, "V": 4, "W": 4, "X": 8, "Y": 4, "Z": 10
}

SUB_MAP = {"1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "8": "₈", "10": "₁₀"}

def get_tile_display(letter):
    val = LETTER_VALUES.get(letter, 0)
    sub = SUB_MAP.get(str(val), "")
    return f"{letter}{sub}"

INITIAL_BAG = list(
    "A"*9 + "B"*2 + "C"*2 + "D"*4 + "E"*12 + "F"*2 + "G"*3 + "H"*2 + "I"*9 + 
    "J"*1 + "K"*1 + "L"*4 + "M"*2 + "N"*6 + "O"*8 + "P"*2 + "Q"*1 + "R"*6 + 
    "S"*4 + "T"*6 + "U"*4 + "V"*2 + "W"*2 + "X"*1 + "Y"*2 + "Z"*1
)

# --- BOARD MULTIPLIERS ---
TW = {(0,0), (0,7), (0,14), (7,0), (7,14), (14,0), (14,7), (14,14)}
DW = {(1,1), (2,2), (3,3), (4,4), (1,13), (2,12), (3,11), (4,10),
      (13,1), (12,2), (11,3), (10,4), (13,13), (12,12), (11,11), (10,10), (7,7)}
TL = {(1,5), (1,9), (5,1), (5,5), (5,9), (5,13),
      (9,1), (9,5), (9,9), (9,13), (13,5), (13,9)}
DL = {(0,3), (0,11), (2,6), (2,8), (3,0), (3,7), (3,14),
      (6,2), (6,6), (6,8), (6,12), (7,3), (7,11),
      (8,2), (8,6), (8,8), (8,12), (11,0), (11,7), (11,14),
      (12,6), (12,8), (14,3), (14,11)}

def get_multiplier(r, c):
    if (r, c) in TW: return "TW"
    if (r, c) in DW: return "DW"
    if (r, c) in TL: return "TL"
    if (r, c) in DL: return "DL"
    return "NORMAL"

def get_cell_info(r, c):
    if (r, c) == (7, 7): return "★", "star"
    if (r, c) in TW: return "3W", "tw"
    if (r, c) in DW: return "2W", "dw"
    if (r, c) in TL: return "3L", "tl"
    if (r, c) in DL: return "2L", "dl"
    return "·", "normal"

# --- DATABASE SETUP ---
DB_FILE = "scrabble_multiplayer.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS games 
                        (room_id TEXT PRIMARY KEY, state TEXT)''')

def get_game(room_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT state FROM games WHERE room_id = ?", (room_id,))
        row = cursor.fetchone()
        return json.loads(row[0]) if row else None

def save_game(room_id, state):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT OR REPLACE INTO games (room_id, state) VALUES (?, ?)", 
                     (room_id, json.dumps(state)))

def draw_tiles(bag, num):
    random.shuffle(bag)
    drawn = bag[:num]
    new_bag = bag[num:]
    return drawn, new_bag

# --- SCORING & WORD ENGINE ---
def find_formed_words(old_board, new_board, placed):
    rows = [r for r, c in placed]
    cols = [c for r, c in placed]
    
    is_horizontal = len(set(rows)) == 1
    is_vertical = len(set(cols)) == 1

    if not is_horizontal and not is_vertical:
        return None, "Placed tiles must be in a single straight row or column."

    words = []

    if is_horizontal:
        r = rows[0]
        c_min, c_max = min(cols), max(cols)
        
        for c in range(c_min, c_max + 1):
            if not new_board[r][c]:
                return None, "Placed tiles cannot have gaps between them."

        left, right = c_min, c_max
        while left > 0 and new_board[r][left - 1]: left -= 1
        while right < BOARD_SIZE - 1 and new_board[r][right + 1]: right += 1
            
        main_word = [(r, c) for c in range(left, right + 1)]
        if len(main_word) > 1:
            words.append(main_word)

        for _, c in placed:
            top, bottom = r, r
            while top > 0 and new_board[top - 1][c]: top -= 1
            while bottom < BOARD_SIZE - 1 and new_board[bottom + 1][c]: bottom += 1
            cross_word = [(row, c) for row in range(top, bottom + 1)]
            if len(cross_word) > 1:
                words.append(cross_word)

    else: # Vertical
        c = cols[0]
        r_min, r_max = min(rows), max(rows)
        
        for r in range(r_min, r_max + 1):
            if not new_board[r][c]:
                return None, "Placed tiles cannot have gaps between them."

        top, bottom = r_min, r_max
        while top > 0 and new_board[top - 1][c]: top -= 1
        while bottom < BOARD_SIZE - 1 and new_board[bottom + 1][c]: bottom += 1

        main_word = [(r, c) for r in range(top, bottom + 1)]
        if len(main_word) > 1:
            words.append(main_word)

        for r, _ in placed:
            left, right = c, c
            while left > 0 and new_board[r][left - 1]: left -= 1
            while right < BOARD_SIZE - 1 and new_board[r][right + 1]: right += 1
            cross_word = [(r, col) for col in range(left, right + 1)]
            if len(cross_word) > 1:
                words.append(cross_word)

    if len(placed) == 1 and not words:
        r, c = placed[0]
        left, right = c, c
        while left > 0 and new_board[r][left - 1]: left -= 1
        while right < BOARD_SIZE - 1 and new_board[r][right + 1]: right += 1
        if right - left > 0: words.append([(r, col) for col in range(left, right + 1)])

        top, bottom = r, r
        while top > 0 and new_board[top - 1][c]: top -= 1
        while bottom < BOARD_SIZE - 1 and new_board[bottom + 1][c]: bottom += 1
        if bottom - top > 0: words.append([(row, c) for row in range(top, bottom + 1)])

    return words, None

def calculate_score(placed, new_board, words):
    total_score = 0
    placed_set = set(placed)

    for word in words:
        word_score = 0
        word_multiplier = 1
        
        for r, c in word:
            tile = new_board[r][c]
            val = LETTER_VALUES.get(tile, 0)
            
            if (r, c) in placed_set:
                mult = get_multiplier(r, c)
                if mult == "DL": val *= 2
                elif mult == "TL": val *= 3
                elif mult == "DW": word_multiplier *= 2
                elif mult == "TW": word_multiplier *= 3
            
            word_score += val
            
        total_score += (word_score * word_multiplier)

    if len(placed) == 7:
        total_score += 50 # Bingo

    return total_score

def create_new_game(room_id, player_name):
    bag = INITIAL_BAG.copy()
    p1_rack, bag = draw_tiles(bag, 7)
    
    state = {
        "board": [["" for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)],
        "bag": bag,
        "players": {
            player_name: {"rack": p1_rack, "score": 0}
        },
        "turn_order": [player_name],
        "current_turn": 0,
        "first_move": True,
        "status": "waiting"
    }
    save_game(room_id, state)
    return state

# --- STREAMLIT UI SETUP ---
st.set_page_config(page_title="Classic Scrabble", layout="wide")
init_db()

# Custom CSS for seamless 1:1 square grid
st.markdown("""
    <style>
    div[data-testid="stHorizontalBlock"],
    .stHorizontalBlock {
        gap: 0px !important;
        margin: 0px !important;
        padding: 0px !important;
    }
    
    .board-frame div[data-testid="stVerticalBlock"] {
        gap: 0px !important;
    }

    div[data-testid="column"],
    .stColumn {
        padding: 0px !important;
        margin: 0px !important;
        min-width: 0px !important;
        flex: 1 1 0% !important;
    }

    .element-container,
    div[data-testid="element-container"] {
        margin: 0px !important;
        padding: 0px !important;
    }

    div.stButton {
        margin: 0px !important;
        padding: 0px !important;
        width: 100% !important;
    }

    div.stButton > button {
        width: 100% !important;
        aspect-ratio: 1 / 1 !important;
        height: auto !important;
        min-height: 0px !important;
        padding: 0px !important;
        margin: 0px !important;
        font-size: 11px !important;
        font-weight: bold !important;
        border-radius: 0px !important;
        border: 1px solid #0a2517 !important;
        box-sizing: border-box !important;
        line-height: 1 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.05s ease-in-out !important;
    }

    .board-frame {
        max-width: 630px;
        margin: 0 auto;
        background-color: #0d2818;
        padding: 8px;
        border-radius: 8px;
        border: 4px solid #081c15;
        box-shadow: 0 6px 20px rgba(0,0,0,0.5);
    }

    .element-container:has(.sq-tw),
    .element-container:has(.sq-dw),
    .element-container:has(.sq-tl),
    .element-container:has(.sq-dl),
    .element-container:has(.sq-star),
    .element-container:has(.sq-normal),
    .element-container:has(.sq-tile),
    .element-container:has(.sq-pending) {
        display: none !important;
    }

    .element-container:has(.sq-tw) + .element-container button {
        background-color: #b81d13 !important;
        color: #ffffff !important;
    }
    .element-container:has(.sq-dw) + .element-container button {
        background-color: #e84393 !important;
        color: #ffffff !important;
    }
    .element-container:has(.sq-tl) + .element-container button {
        background-color: #0984e3 !important;
        color: #ffffff !important;
    }
    .element-container:has(.sq-dl) + .element-container button {
        background-color: #74b9ff !important;
        color: #1e272e !important;
    }
    .element-container:has(.sq-star) + .element-container button {
        background-color: #e84393 !important;
        color: #ffeaa7 !important;
        font-size: 14px !important;
    }
    .element-container:has(.sq-normal) + .element-container button {
        background-color: #1b4332 !important;
        color: #40916c !important;
    }

    .element-container:has(.sq-tile) + .element-container button {
        background-color: #f5e6ca !important;
        color: #2c3e50 !important;
        font-size: 13px !important;
        font-weight: 900 !important;
        border: 1px solid #b08968 !important;
        box-shadow: inset 0 -2px 0 #b08968 !important;
    }

    .element-container:has(.sq-pending) + .element-container button {
        background-color: #ffeaa7 !important;
        color: #d63031 !important;
        font-size: 13px !important;
        font-weight: 900 !important;
        border: 1px solid #fdcb6e !important;
        box-shadow: inset 0 0 4px #fdcb6e !important;
    }

    .rack-tray {
        background-color: #5c3d2e;
        padding: 10px;
        border-radius: 6px;
        border: 2px solid #3d2314;
        max-width: 450px;
        margin: 0 auto 15px auto;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🔠 Online Classic Scrabble")

if "username" not in st.session_state: st.session_state.username = ""
if "room_id" not in st.session_state: st.session_state.room_id = ""
if "selected_rack_idx" not in st.session_state: st.session_state.selected_rack_idx = None
if "pending_placements" not in st.session_state: st.session_state.pending_placements = {}

with st.sidebar:
    st.header("Game Lobby")
    username = st.text_input("Your Name", value=st.session_state.username)
    room_id = st.text_input("Room ID", value=st.session_state.room_id)
    
    if st.button("Join / Create Game"):
        if username and room_id:
            st.session_state.username = username
            st.session_state.room_id = room_id
            st.session_state.pending_placements = {}
            st.session_state.selected_rack_idx = None
            
            game = get_game(room_id)
            if not game:
                create_new_game(room_id, username)
                st.success(f"Room '{room_id}' created!")
            elif username not in game["players"]:
                if len(game["players"]) >= 2:
                    st.error("Room is full!")
                else:
                    p2_rack, game["bag"] = draw_tiles(game["bag"], 7)
                    game["players"][username] = {"rack": p2_rack, "score": 0}
                    game["turn_order"].append(username)
                    game["status"] = "playing"
                    save_game(room_id, game)
                    st.success("Joined game!")
            st.rerun()

    if st.session_state.room_id:
        if st.button("🔄 Manual Refresh"):
            st.rerun()

    st.markdown("---")
    st.markdown("**Board Legend:**")
    st.markdown("🔴 **3W** = Triple Word Score")
    st.markdown("💖 **2W** = Double Word Score")
    st.markdown("🔵 **3L** = Triple Letter Score")
    st.markdown("🔷 **2L** = Double Letter Score")
    st.markdown("★ = Start Square")

if st.session_state.room_id and st.session_state.username:
    game = get_game(st.session_state.room_id)
    me = st.session_state.username
    
    if not game:
        st.warning("Game not found.")
    elif game["status"] == "waiting":
        st.info("Waiting for another player to join...")
        time.sleep(3)
        st.rerun()
    else:
        # Scoreboard
        cols = st.columns(3)
        for i, p in enumerate(game["turn_order"]):
            cols[i].metric(label=f"👤 {p}", value=game["players"][p]["score"])
        cols[2].metric(label="📦 Bag Tiles", value=len(game["bag"]))

        current_player = game["turn_order"][game["current_turn"]]
        is_my_turn = (current_player == me)
        
        if is_my_turn:
            st.success("✨ It's your turn!")
        else:
            st.warning(f"⏳ Waiting for {current_player} to play... (Auto-refreshing)")

        # --- PLAYER RACK ---
        st.subheader("Your Rack")
        my_rack = game["players"][me]["rack"]
        used_rack_indices = {data["rack_idx"] for data in st.session_state.pending_placements.values()}
        
        st.markdown('<div class="rack-tray">', unsafe_allow_html=True)
        rack_cols = st.columns(7)
        for idx, tile in enumerate(my_rack):
            display_str = get_tile_display(tile)
            if idx in used_rack_indices:
                rack_cols[idx].button(f"({tile})", key=f"rack_{idx}", disabled=True)
            else:
                is_selected = (st.session_state.selected_rack_idx == idx)
                label = f"🟡 {display_str}" if is_selected else display_str
                
                if rack_cols[idx].button(label, key=f"rack_{idx}", disabled=not is_my_turn):
                    st.session_state.selected_rack_idx = idx
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # --- BOARD DISPLAY ---
        st.subheader("The Board")
        
        st.markdown('<div class="board-frame">', unsafe_allow_html=True)
        for r in range(BOARD_SIZE):
            grid_cols = st.columns(BOARD_SIZE)
            for c in range(BOARD_SIZE):
                pos = (r, c)
                perm_tile = game["board"][r][c]
                pending_info = st.session_state.pending_placements.get(pos)

                with grid_cols[c]:
                    if perm_tile != "":
                        st.markdown('<div class="sq-tile"></div>', unsafe_allow_html=True)
                        st.button(get_tile_display(perm_tile), key=f"b_{r}_{c}", disabled=True)
                    elif pending_info is not None:
                        pending_tile = pending_info["letter"]
                        st.markdown('<div class="sq-pending"></div>', unsafe_allow_html=True)
                        if st.button(get_tile_display(pending_tile), key=f"b_{r}_{c}"):
                            del st.session_state.pending_placements[pos]
                            st.rerun()
                    else:
                        cell_label, sq_type = get_cell_info(r, c)
                        st.markdown(f'<div class="sq-{sq_type}"></div>', unsafe_allow_html=True)
                        
                        if st.button(cell_label, key=f"b_{r}_{c}", disabled=not is_my_turn):
                            if st.session_state.selected_rack_idx is not None:
                                sel_idx = st.session_state.selected_rack_idx
                                st.session_state.pending_placements[pos] = {
                                    "letter": my_rack[sel_idx],
                                    "rack_idx": sel_idx
                                }
                                st.session_state.selected_rack_idx = None
                                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # --- ACTIONS ---
        st.write("")
        if is_my_turn:
            action_cols = st.columns([1, 1, 2])
            
            with action_cols[0]:
                if st.button("🚀 Submit Move", type="primary"):
                    placed_coords = list(st.session_state.pending_placements.keys())
                    placed_tiles = [v["letter"] for v in st.session_state.pending_placements.values()]
                    valid_move = True

                    if not placed_coords:
                        st.warning("You haven't placed any tiles yet!")
                        valid_move = False

                    if valid_move and game.get("first_move", True):
                        if (7, 7) not in placed_coords:
                            st.error("First move must cover the center star (★)!")
                            valid_move = False

                    if valid_move and not game.get("first_move", True):
                        touches_existing = False
                        for r, c in placed_coords:
                            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                nr, nc = r + dr, c + dc
                                if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE:
                                    if game["board"][nr][nc] != "" and (nr, nc) not in placed_coords:
                                        touches_existing = True
                                        break
                        if not touches_existing:
                            st.error("Your word must connect to an existing tile on the board!")
                            valid_move = False

                    new_board = [row.copy() for row in game["board"]]
                    for (r, c), data in st.session_state.pending_placements.items():
                        new_board[r][c] = data["letter"]

                    if valid_move:
                        words, err_msg = find_formed_words(game["board"], new_board, placed_coords)
                        if err_msg:
                            st.error(err_msg)
                            valid_move = False
                        elif not words:
                            st.error("Move must form at least one valid word!")
                            valid_move = False

                    if valid_move:
                        turn_score = calculate_score(placed_coords, new_board, words)
                        
                        used_indices = {v["rack_idx"] for v in st.session_state.pending_placements.values()}
                        remaining_rack = [tile for i, tile in enumerate(my_rack) if i not in used_indices]
                        
                        drawn, game["bag"] = draw_tiles(game["bag"], len(placed_tiles))
                        game["players"][me]["rack"] = remaining_rack + drawn
                        
                        game["board"] = new_board
                        game["players"][me]["score"] += turn_score
                        game["first_move"] = False
                        game["current_turn"] = (game["current_turn"] + 1) % len(game["turn_order"])
                        
                        save_game(st.session_state.room_id, game)
                        
                        st.session_state.pending_placements = {}
                        st.session_state.selected_rack_idx = None
                        
                        word_strings = ["".join([new_board[r][c] for r, c in w]) for w in words]
                        st.success(f"Move accepted! Formed: {', '.join(word_strings)}. +{turn_score} pts!")
                        time.sleep(2)
                        st.rerun()

            with action_cols[1]:
                if st.button("↩️ Undo Placements"):
                    st.session_state.pending_placements = {}
                    st.session_state.selected_rack_idx = None
                    st.rerun()

            with action_cols[2]:
                if st.button("🔄 Pass / Swap Rack"):
                    game["bag"].extend(my_rack)
                    game["players"][me]["rack"], game["bag"] = draw_tiles(game["bag"], 7)
                    game["current_turn"] = (game["current_turn"] + 1) % len(game["turn_order"])
                    save_game(st.session_state.room_id, game)
                    st.session_state.pending_placements = {}
                    st.session_state.selected_rack_idx = None
                    st.rerun()
        else:
            # AUTO-POLLING LOOP (Runs every 3s only when waiting for opponent)
            time.sleep(3)
            st.rerun()
