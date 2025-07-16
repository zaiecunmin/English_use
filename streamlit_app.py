import streamlit as st
import json
import random
import os
import base64
from pathlib import Path
import pyttsx3
import time
import platform

if platform.system() == "Linux":
    os.system('apt-get install -y espeak')

# 应用标题和配置
st.set_page_config(page_title="英语单词背诵工具", layout="wide")
st.title("📚 英语单词背诵工具")

# 常量定义
USER_DATA_DIR = Path("users")
WORD_DATA_FILE = Path("main.json")
AUDIO_DIR = Path("audio")
USER_DATA_DIR.mkdir(exist_ok=True, parents=True)
AUDIO_DIR.mkdir(exist_ok=True, parents=True)

# 初始化session状态
def init_session_state():
    session_defaults = {
        'current_word': None,
        'show_answer': False,
        'word_list': [],
        'filtered_words': [],
        'study_mode': "flashcard",
        'current_user': None,
        'user_data': {},
        'word_loaded': False,
        'unit_filter': [],
        'type_filter': [],
        'review_mode': False,
        'quiz_options': None,
        'quiz_answer': None,
        'flashcard_feedback': None,
        'voice_gender': "female",
        'voice_speed': 150,
        'audio_generated': False,
        'audio_refreshed': False,
        'last_voice_settings': {"gender": "female", "speed": 150},  # 记录上次语音设置
        'current_audio_file': None  # 存储当前音频文件路径
    }
    
    for key, value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# 用户管理函数
def load_user_data(user_id):
    user_file = USER_DATA_DIR / f"{user_id}.json"
    if user_file.exists():
        try:
            with open(user_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"known_words": {}, "word_stats": {}}
    return {"known_words": {}, "word_stats": {}}

def save_user_data(user_id, data):
    user_file = USER_DATA_DIR / f"{user_id}.json"
    with open(user_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_all_users():
    return [f.stem for f in USER_DATA_DIR.glob("*.json") if f.is_file()]

# 加载单词数据
def load_word_data():
    if st.session_state.word_loaded:
        return
    
    try:
        if WORD_DATA_FILE.exists():
            with open(WORD_DATA_FILE, 'r', encoding='utf-8') as f:
                word_data = json.load(f)
                st.session_state.word_list = word_data
                st.session_state.filtered_words = word_data.copy()
                st.session_state.word_loaded = True
        else:
            st.error(f"未找到单词文件: {WORD_DATA_FILE}")
    except Exception as e:
        st.error(f"单词文件解析错误: {e}")

# 生成单词发音
def generate_audio(word, force_refresh=False):
    # 使用当前语音设置创建音频文件名
    gender = st.session_state.voice_gender
    speed = st.session_state.voice_speed
    audio_file = AUDIO_DIR / f"{word['id']}_{gender}_{speed}.wav"
    
    # 如果强制刷新或文件不存在，则生成新音频
    if force_refresh or not audio_file.exists():
        try:
            # 如果文件存在且需要强制刷新，先删除旧文件
            if audio_file.exists() and force_refresh:
                try:
                    # 尝试删除文件，如果失败则等待后重试
                    for attempt in range(3):
                        try:
                            audio_file.unlink()
                            break
                        except PermissionError:
                            if attempt < 2:
                                time.sleep(0.5)  # 等待0.5秒后重试
                            else:
                                st.warning(f"无法删除旧音频文件，可能是文件正在使用中: {audio_file.name}")
                except Exception as e:
                    st.warning(f"删除旧音频文件失败: {e}")
            
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            
            if gender == "female":
                for voice in voices:
                    if "female" in voice.name.lower():
                        engine.setProperty('voice', voice.id)
                        break
            else:
                for voice in voices:
                    if "male" in voice.name.lower():
                        engine.setProperty('voice', voice.id)
                        break
            
            engine.setProperty('rate', speed)
            engine.save_to_file(word['en'], str(audio_file))
            engine.runAndWait()
            
            return audio_file
        except Exception as e:
            st.error(f"语音生成失败: {e}")
            return None
    else:
        return audio_file

# 获取音频文件的base64编码
def get_audio_base64(audio_file):
    if audio_file and audio_file.exists():
        with open(audio_file, 'rb') as f:
            audio_bytes = f.read()
        return base64.b64encode(audio_bytes).decode('utf-8')
    return None

# 加权随机选择单词
def get_weighted_random_word(word_list, user_stats):
    if not word_list:
        return None
    
    weights = []
    for word in word_list:
        word_id = str(word["id"])
        stats = user_stats.get(word_id, {"correct": 0, "wrong": 0})
        weight = 10 + (stats["wrong"] * 3) - stats["correct"]
        weight = max(1, weight)
        weights.append(weight)
    
    total_weight = sum(weights)
    if total_weight <= 0:
        return random.choice(word_list)
    
    rand = random.uniform(0, total_weight)
    cumulative = 0
    
    for i, weight in enumerate(weights):
        cumulative += weight
        if rand < cumulative:
            return word_list[i]
    
    return random.choice(word_list)

# 筛选选项
def apply_filters():
    # 确保单词列表存在
    if not st.session_state.word_list:
        st.session_state.filtered_words = []
        return
    
    filtered = st.session_state.word_list.copy()
    
    # 单元筛选
    if st.session_state.unit_filter:
        # 将单词单元转换为字符串进行比较
        filtered = [w for w in filtered if str(w.get("unit", "")) in st.session_state.unit_filter]
    
    # 词性筛选
    if st.session_state.type_filter:
        filtered = [w for w in filtered if w.get("type", "") in st.session_state.type_filter]
    
    # 复习模式筛选
    if st.session_state.review_mode:
        # 确保用户数据存在
        user_data = st.session_state.user_data
        if "known_words" in user_data:
            # 只保留标记为已掌握的单词
            filtered = [w for w in filtered if str(w["id"]) in user_data["known_words"]]
    
    st.session_state.filtered_words = filtered

# 获取新单词
def get_new_word():
    if st.session_state.filtered_words and st.session_state.current_user:
        st.session_state.current_word = get_weighted_random_word(
            st.session_state.filtered_words,
            st.session_state.user_data.get("word_stats", {})
        )
        st.session_state.show_answer = False
        st.session_state.flashcard_feedback = None
        st.session_state.quiz_options = None
        st.session_state.quiz_answer = None
        st.session_state.audio_generated = False
        st.session_state.audio_refreshed = False
        st.session_state.current_audio_file = None  # 重置当前音频文件
    else:
        st.warning("没有符合条件的单词，请检查筛选条件或用户设置。")

# 更新单词统计
def update_word_stats(word_id, is_correct):
    if not st.session_state.current_user:
        return
    
    word_id = str(word_id)
    user_data = st.session_state.user_data
    
    if "word_stats" not in user_data:
        user_data["word_stats"] = {}
    
    if word_id not in user_data["word_stats"]:
        user_data["word_stats"][word_id] = {"correct": 0, "wrong": 0}
    
    if is_correct:
        user_data["word_stats"][word_id]["correct"] += 1
    else:
        user_data["word_stats"][word_id]["wrong"] += 1
    
    save_user_data(st.session_state.current_user, user_data)
    st.session_state.user_data = user_data

# 标记单词
def mark_word(known=True):
    if st.session_state.current_word and st.session_state.current_user:
        word_id = str(st.session_state.current_word["id"])
        user_data = st.session_state.user_data
        
        if "known_words" not in user_data:
            user_data["known_words"] = {}
        
        if known:
            user_data["known_words"][word_id] = True
        elif word_id in user_data["known_words"]:
            del user_data["known_words"][word_id]
        
        save_user_data(st.session_state.current_user, user_data)
        st.session_state.user_data = user_data

# 单词卡片模式
def flashcard_mode():
    if not st.session_state.current_word and st.session_state.filtered_words:
        get_new_word()
        st.rerun()
    
    if st.session_state.current_word:
        word = st.session_state.current_word
        
        # 检查语音设置是否变化
        current_settings = {
            "gender": st.session_state.voice_gender,
            "speed": st.session_state.voice_speed
        }
        
        # 如果语音设置变化或需要刷新，重新生成音频
        if (st.session_state.show_answer and 
            (not st.session_state.audio_generated or 
             st.session_state.audio_refreshed or
             current_settings != st.session_state.last_voice_settings)):
            
            # 强制刷新音频（如果设置了刷新标志）
            force_refresh = st.session_state.audio_refreshed or (current_settings != st.session_state.last_voice_settings)
            generated_audio = generate_audio(
                word, 
                force_refresh=force_refresh
            )
            if generated_audio:
                st.session_state.current_audio_file = generated_audio
                st.session_state.audio_generated = True
                st.session_state.audio_refreshed = False
                st.session_state.last_voice_settings = current_settings  # 更新上次设置
            else:
                st.warning("音频生成失败，请重试")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("英语单词")
            st.markdown(f"## {word['en']}")
            st.caption(f"词性: {word['type']} | 单元: {word['unit']}")
            
            if st.session_state.show_answer:
                st.subheader("详细信息")
                
                # 使用存储的音频文件路径
                audio_file = st.session_state.current_audio_file
                
                if audio_file and audio_file.exists():
                    audio_base64 = get_audio_base64(audio_file)
                    if audio_base64:
                        st.markdown(f"""
                        <audio controls autoplay id="word_audio">
                            <source src="data:audio/wav;base64,{audio_base64}" type="audio/wav">
                            您的浏览器不支持音频元素。
                        </audio>
                        """, unsafe_allow_html=True)
                        
                        # 添加刷新音频按钮
                        if st.button("🔄 刷新音频", key="btn_refresh_audio", 
                                    help="使用当前语音设置重新生成单词发音"):
                            st.session_state.audio_refreshed = True
                            st.rerun()
                    else:
                        st.warning("无法加载音频文件")
                else:
                    st.warning("音频文件未生成")
                
                st.success(f"**中文释义**: {word['zh']}")
                st.info(f"**词性**: {word['type']}")
                st.info(f"**单元**: {word['unit']}")
                st.info(f"**ID**: {word['id']}")
        
        with col2:
            st.subheader("操作")
            
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                if st.button("显示答案", key="btn_show_answer", use_container_width=True):
                    st.session_state.show_answer = True
                    st.rerun()
            with col_btn2:
                if st.button("认识", key="btn_know", use_container_width=True):
                    st.session_state.show_answer = True
                    st.session_state.flashcard_feedback = True
                    mark_word(True)
                    st.rerun()
            with col_btn3:
                if st.button("不认识", key="btn_dont_know", use_container_width=True):
                    st.session_state.show_answer = True
                    st.session_state.flashcard_feedback = False
                    mark_word(False)
                    st.rerun()
            
            if st.button("下一个单词", 
                         disabled=not st.session_state.show_answer,
                         key="btn_next_word",
                         use_container_width=True):
                get_new_word()
                st.rerun()
            
            st.info("提示: 单词卡片操作不会影响单词出现频率")

# 生成选择题选项
def generate_quiz_options():
    if st.session_state.current_word and not st.session_state.quiz_options:
        word = st.session_state.current_word
        options = [word['zh']]
        
        while len(options) < 4 and len(options) < len(st.session_state.filtered_words):
            random_word = random.choice(st.session_state.filtered_words)
            if random_word['zh'] not in options and random_word['id'] != word['id']:
                options.append(random_word['zh'])
        
        random.shuffle(options)
        st.session_state.quiz_options = options
        st.session_state.quiz_answer = word['zh']

# 选择题模式
def quiz_mode():
    if not st.session_state.current_word and st.session_state.filtered_words:
        get_new_word()
        st.rerun()
    
    if st.session_state.current_word:
        word = st.session_state.current_word
        st.subheader("选择题模式")
        st.write(f"请选择单词 **{word['en']}** 的正确中文释义：")
        
        generate_quiz_options()
        
        selected = st.radio("选项", st.session_state.quiz_options, key="radio_quiz_options")
        
        if st.button("提交", key="btn_submit_quiz"):
            is_correct = selected == st.session_state.quiz_answer
            update_word_stats(word["id"], is_correct)
            
            if is_correct:
                st.success("✅ 回答正确！")
            else:
                st.error(f"❌ 回答错误，正确答案是: {st.session_state.quiz_answer}")
            
            st.write(f"词性: {word['type']} | 单元: {word['unit']}")
            
            if st.button("下一题", key="btn_next_quiz", use_container_width=True):
                get_new_word()
                st.rerun()

# 拼写测试模式
def spelling_mode():
    if not st.session_state.current_word and st.session_state.filtered_words:
        get_new_word()
        st.rerun()
    
    if st.session_state.current_word:
        word = st.session_state.current_word
        st.subheader("拼写测试模式")
        st.write(f"请根据中文释义拼写对应的英文单词：")
        st.info(f"{word['zh']} ({word['type']})")
        
        user_input = st.text_input("输入英文单词", key="input_spelling").strip()
        
        if st.button("检查", key="btn_check_spelling"):
            is_correct = user_input.lower() == word['en'].lower()
            update_word_stats(word["id"], is_correct)
            
            if is_correct:
                st.success("✅ 拼写正确！")
            else:
                st.error(f"❌ 拼写错误，正确答案是: {word['en']}")
            
            st.write(f"单元: {word['unit']}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("认识", key="btn_spelling_known", use_container_width=True):
                    mark_word(True)
                    st.rerun()
                if st.button("不认识", key="btn_spelling_unknown", use_container_width=True):
                    mark_word(False)
                    st.rerun()
            with col2:
                if st.button("下一题", key="btn_spelling_next", use_container_width=True):
                    get_new_word()
                    st.rerun()

# 语音设置侧边栏
def voice_settings():
    with st.sidebar.expander("🔊 语音设置", expanded=True):
        # 语音性别选择
        gender = st.radio("语音性别", ["男声", "女声"], 
                         index=0 if st.session_state.voice_gender == "male" else 1,
                         key="radio_voice_gender")
        
        st.session_state.voice_gender = "male" if gender == "男声" else "female"
        
        # 语速设置
        speed = st.slider("语速", 80, 300, st.session_state.voice_speed, 
                         key="slider_voice_speed",
                         help="数值越大语速越快")
        st.session_state.voice_speed = speed
        
        # 清除音频缓存按钮
        if st.button("清除音频缓存", key="btn_clear_audio_cache"):
            deleted_files = 0
            for file in AUDIO_DIR.glob("*.wav"):
                try:
                    # 尝试删除文件，如果失败则跳过
                    for attempt in range(3):
                        try:
                            file.unlink()
                            deleted_files += 1
                            break
                        except PermissionError:
                            if attempt < 2:
                                time.sleep(0.5)  # 等待0.5秒后重试
                            else:
                                st.warning(f"无法删除文件，可能是文件正在使用中: {file.name}")
                except Exception as e:
                    st.warning(f"删除文件失败: {e}")
            
            st.toast(f"已删除 {deleted_files} 个音频缓存文件！", icon="✅")
            
            # 如果当前有单词且显示答案，重新生成音频
            if st.session_state.show_answer and st.session_state.current_word:
                st.session_state.audio_generated = False
                st.rerun()

# 用户管理界面
def user_management():
    with st.sidebar.expander("👤 用户管理", expanded=True):
        all_users = get_all_users()
        new_user = st.text_input("新建用户名", key="input_new_user")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("创建用户", key="btn_create_user", use_container_width=True) and new_user:
                if new_user in all_users:
                    st.error("用户名已存在")
                elif new_user:
                    save_user_data(new_user, {"known_words": {}, "word_stats": {}})
                    st.toast(f"用户 {new_user} 创建成功！", icon="✅")
                    st.session_state.current_user = new_user
                    st.session_state.user_data = load_user_data(new_user)
                    st.rerun()
        
        with col2:
            if st.button("删除当前用户", key="btn_delete_user", use_container_width=True) and st.session_state.current_user:
                user_file = USER_DATA_DIR / f"{st.session_state.current_user}.json"
                if user_file.exists():
                    try:
                        os.remove(user_file)
                        st.toast(f"用户 {st.session_state.current_user} 已删除", icon="✅")
                        st.session_state.current_user = None
                        st.session_state.user_data = {}
                        st.rerun()
                    except Exception as e:
                        st.error(f"删除用户失败: {e}")
        
        selected_user = st.selectbox(
            "选择用户",
            [""] + all_users,
            index=0 if not st.session_state.current_user else all_users.index(st.session_state.current_user) + 1,
            key="select_user"
        )
        
        if selected_user and selected_user != st.session_state.current_user:
            st.session_state.current_user = selected_user
            st.session_state.user_data = load_user_data(selected_user)
            st.rerun()
        
        if st.session_state.current_user:
            st.info(f"当前用户: {st.session_state.current_user}")
            
            if st.button("重置学习进度", key="btn_reset_progress", use_container_width=True):
                st.session_state.user_data = {"known_words": {}, "word_stats": {}}
                save_user_data(st.session_state.current_user, st.session_state.user_data)
                st.toast("学习进度已重置！", icon="✅")
                st.rerun()

# 筛选选项侧边栏
def filter_sidebar():
    if st.session_state.word_list:
        # 获取所有单元（转换为字符串）
        all_units = sorted(set(str(word.get("unit", "")) for word in st.session_state.word_list))
        # 获取所有词性
        all_types = sorted(set(word.get("type", "") for word in st.session_state.word_list))
        
        with st.sidebar.expander("🔍 筛选选项", expanded=True):
            # 单元筛选器
            selected_units = st.multiselect(
                "选择单元",
                options=all_units,
                default=st.session_state.unit_filter,
                key="multiselect_unit_filter"
            )
            st.session_state.unit_filter = selected_units
            
            # 词性筛选器
            selected_types = st.multiselect(
                "选择词性",
                options=all_types,
                default=st.session_state.type_filter,
                key="multiselect_type_filter"
            )
            st.session_state.type_filter = selected_types
            
            # 复习模式
            review_mode = st.checkbox(
                "仅复习标记的单词",
                value=st.session_state.review_mode,
                key="checkbox_review_mode"
            )
            st.session_state.review_mode = review_mode
        
        # 应用筛选条件
        apply_filters()
        
        st.sidebar.markdown(f"📊 当前单词总数: {len(st.session_state.filtered_words)}")

# 学习模式选择
def study_mode_selector():
    if st.session_state.word_list:
        mode_mapping = {
            "单词卡片": "flashcard",
            "选择题": "quiz",
            "拼写测试": "spelling"
        }
        
        mode_names = list(mode_mapping.keys())
        current_mode_name = [k for k, v in mode_mapping.items() if v == st.session_state.study_mode][0]
        
        selected_mode = st.sidebar.radio(
            "选择学习模式",
            mode_names,
            index=mode_names.index(current_mode_name),
            key="radio_study_mode"
        )
        
        st.session_state.study_mode = mode_mapping[selected_mode]

# 统计信息侧边栏
def stats_sidebar():
    if st.session_state.word_list and st.session_state.current_user:
        with st.sidebar.expander("📈 学习统计", expanded=False):
            total_words = len(st.session_state.word_list)
            known_count = len(st.session_state.user_data.get("known_words", {}))
            progress = known_count / total_words if total_words > 0 else 0
            
            st.write(f"总单词数: {total_words}")
            st.write(f"已掌握: {known_count}")
            st.progress(min(1.0, progress))
            
            word_stats = st.session_state.user_data.get("word_stats", {})
            if word_stats:
                hardest_words = []
                for word_id, stats in word_stats.items():
                    word = next((w for w in st.session_state.word_list if str(w["id"]) == word_id), None)
                    if word:
                        total_attempts = stats["correct"] + stats["wrong"]
                        if total_attempts > 0:
                            error_rate = stats["wrong"] / total_attempts
                            hardest_words.append((word, error_rate, stats))
                
                if hardest_words:
                    hardest_words.sort(key=lambda x: x[1], reverse=True)
                    st.write("最难单词 (按错误率排序):")
                    for word, error_rate, stats in hardest_words[:5]:
                        st.write(f"- **{word['en']}** ({word['zh']}): 错误率 {error_rate:.0%} (✓{stats['correct']} ✗{stats['wrong']})")

# 单词列表展示
def word_list_display():
    if st.session_state.word_list and st.sidebar.checkbox("显示单词列表", key="checkbox_show_word_list"):
        st.subheader("单词列表")
        
        cols = st.columns(3)
        for idx, word in enumerate(st.session_state.filtered_words):
            with cols[idx % 3]:
                word_id = str(word["id"])
                is_known = word_id in st.session_state.user_data.get("known_words", {})
                stats = st.session_state.user_data.get("word_stats", {}).get(word_id, {"correct": 0, "wrong": 0})
                
                with st.expander(f"{word['en']} - {word['zh']} {'✅' if is_known else ''}", key=f"expander_{word['id']}"):
                    st.write(f"**词性**: {word['type']}")
                    st.write(f"**单元**: {word['unit']}")
                    st.write(f"**正确**: {stats['correct']} 次")
                    st.write(f"**错误**: {stats['wrong']} 次")
                    
                    if st.button("播放发音", key=f"btn_play_{word['id']}", use_container_width=True):
                        audio_file = generate_audio(
                            word
                        )
                        if audio_file:
                            audio_base64 = get_audio_base64(audio_file)
                            if audio_base64:
                                st.markdown(f"""
                                <audio controls autoplay>
                                    <source src="data:audio/wav;base64,{audio_base64}" type="audio/wav">
                                </audio>
                                """, unsafe_allow_html=True)
                    
                    if st.button(
                        "✅ 已掌握" if is_known else "标记为已掌握",
                        key=f"btn_mark_{word['id']}",
                        type="primary" if is_known else "secondary",
                        use_container_width=True
                    ):
                        if is_known:
                            mark_word(False)
                        else:
                            mark_word(True)
                        st.rerun()

# 主界面
def main():
    load_word_data()
    
    user_management()
    voice_settings()
    
    if st.session_state.current_user:
        filter_sidebar()
        study_mode_selector()
        stats_sidebar()
        
        if not st.session_state.word_loaded:
            st.info("请确保main.json文件存在并格式正确")
            st.json({
                "en": "example",
                "zh": "例子",
                "unit": "1",
                "type": "n.",
                "id": 1
            }, expanded=False)
        else:
            if not st.session_state.filtered_words:
                st.warning("没有符合条件的单词，请调整筛选条件。")
                if st.button("重置筛选条件", key="btn_reset_filters"):
                    st.session_state.unit_filter = []
                    st.session_state.type_filter = []
                    st.session_state.review_mode = False
                    apply_filters()
                    st.rerun()
            else:
                if st.session_state.study_mode == "flashcard":
                    flashcard_mode()
                elif st.session_state.study_mode == "quiz":
                    quiz_mode()
                elif st.session_state.study_mode == "spelling":
                    spelling_mode()
        
        word_list_display()

if __name__ == "__main__":
    main()
