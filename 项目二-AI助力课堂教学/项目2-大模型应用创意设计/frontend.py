import streamlit as st
from prepare import prepare
from teacher import Teacher
from util import connect_db
from config import config
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from student import in_db, Student
from io import BytesIO

if 'stage' not in st.session_state:
    st.session_state.stage = 0

if 'student_name' not in st.session_state:
    st.session_state.student_name = ''

if 'questions' not in st.session_state:
    st.session_state.questions = []

st.markdown(
    """
    <style>
        img {
            border-radius: 15px; /* 调整这里的值以改变圆角的程度 */
        }
    </style>
    """,
    unsafe_allow_html=True
)

if st.session_state.stage == 0:
    # 主页
    st.sidebar.image("项目2-大模型应用创意设计/figures/image1.jpg")
    st.title("欢迎使用智慧课堂AI")
    st.write("请点击下方按钮开始使用")
    if st.button("重置数据库环境"):
        prepare()
        st.success("数据库环境已重置！")
    if st.button("教师端"):
        st.session_state.stage = 1
    if st.button("学生端"):
        st.session_state.stage = 2

elif st.session_state.stage == 1:
    # 教师端发布题目
    st.sidebar.image("项目2-大模型应用创意设计/figures/image2.jpg")
    teacher = Teacher()
    # 检查是否有题目没有终止答题
    with connect_db() as con:
        cur = con.cursor()
        cur.execute("USE charging_db;")
        cur.execute("SELECT * FROM questions;")
        if cur.rowcount > 0:
            st.error("有题目未终止答题！")
            if st.button("终止答题"):
                st.session_state.stage = 4

    # 选择题目
    st.write("题目列表如下：\n")
    with open(config['question'], 'r', encoding='utf-8') as file:
        questions = [line.strip() for line in file]
    for i, question in enumerate(questions, 1):
        st.write(f"{i}. {question}")
    question_id = st.text_input("请选择要发布的题目编号")
    if st.button("发布题目"):
        question_id = int(question_id)
        question = questions[int(question_id) - 1]
        teacher.publish_question(question, question_id)
        st.success(f"题目 {question} 发布成功！")
        st.session_state.stage = 3

elif st.session_state.stage == 2:
    # 学生端回答题目
    st.sidebar.image("项目2-大模型应用创意设计/figures/image3.jpg")
    if st.button("返回主页"):
        st.session_state.stage = 0
    student_name = st.text_input("请输入你的姓名")
    answer = ""
    if st.button("开始答题"):
        student_name = student_name.strip()
        if not in_db(student_name):
            st.error("你不在学生名单中！")
        else:
            st.success("成功登陆！")
            with connect_db() as con:
                cur = con.cursor()
                cur.execute("USE charging_db;")
                cur.execute("SELECT * FROM questions;")
                questions = cur.fetchone()
                if cur.rowcount == 0:
                    st.error("暂无题目！")
                else:
                    st.session_state.student_name = student_name
                    st.session_state.stage = 6

elif st.session_state.stage == 3:
    # 教师端查看当前答题情况
    st.sidebar.image("项目2-大模型应用创意设计/figures/image4.jpg")
    teacher = Teacher()
    if st.button("刷新当前答题情况"):
        info = teacher.view_current_situation()
        if len(info) == 0:
            st.error("暂无题目正在答题！")
            st.session_state.stage = 1
        else:
            question_id, question, student_count, answered_count = info
            st.write(f"当前正在答题的题目：{question_id}. {question}")
            st.write(f"该题目已有 {answered_count} 人提交答案，共 {student_count} 人。")
    if st.button("返回主页"):
        st.session_state.stage = 0
    if st.button("终止答题"):
        st.session_state.stage = 4

elif st.session_state.stage == 4:
    # 教师端终止答题
    st.sidebar.image("项目2-大模型应用创意设计/figures/image5.jpg")
    teacher = Teacher()
    if st.button("返回主页"):
        st.session_state.stage = 0
    if st.button("终止答题"):
        with connect_db() as con:
            cur = con.cursor()
            cur.execute("USE charging_db;")
            cur.execute("SELECT * FROM questions;")
            if cur.rowcount == 0:
                st.error("暂无题目正在答题！")
            else:
                question = cur.fetchone()
                question_id, question, standard_answer = question
                st.write(f"当前正在答题的题目：{question_id}. {question}")
                cur.execute("DELETE FROM questions;")
                st.success("题目 %s 的答题已终止！" % question)
                con.commit()
                teacher.stop_answer(question_id, question, standard_answer)
                st.success("已生成总体答题情况！")
                if st.button("查看总体答题情况"):
                    st.session_state.stage = 5
elif st.session_state.stage == 5:
    # 教师端查看总体答题情况
    st.sidebar.image("项目2-大模型应用创意设计/figures/image1.jpg")
    if st.button("返回主页"):
        st.session_state.stage = 0
    teacher = Teacher()
    with connect_db() as con:
        cur = con.cursor()
        cur.execute("USE charging_db;")
        cur.execute("SELECT * FROM overall_situations;")
        overall_situations = cur.fetchall()
    options = [f"问题 {question_id}" for question_id, _, _ in overall_situations]
    choice = st.selectbox('请选择要查看的题目编号:', options)
    st.write(f'你选择查看的题目编号是: {choice}')
    question_id, keywords_freq_pre, analysis = overall_situations[options.index(choice)]
    keywords_freq_list = keywords_freq_pre.split(',')
    keywords_freq = dict()
    for keyword_freq in keywords_freq_list:
        keyword, freq = keyword_freq.split(':')
        keywords_freq[keyword] = float(freq)

    # 创建词云对象
    wordcloud = WordCloud(
        width=600,
        height=600,
        background_color='white',
        font_path='font/msyh.ttc',
        max_words=200,
        max_font_size=100,
        random_state=42
    ).generate_from_frequencies(keywords_freq)

    # 显示词云图
    buffer = BytesIO()
    plt.figure(figsize=(10, 10))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    st.image(buffer, caption='Word Cloud', use_column_width=True)

    st.write(f"问题 {question_id} 的总体答题情况：")
    st.write(analysis)

elif st.session_state.stage == 6:
    st.sidebar.image("项目2-大模型应用创意设计/figures/image2.jpg")
    if st.button("返回主页"):
        st.session_state.stage = 0
    # 读取发布的题目
    with connect_db() as con:
        cur = con.cursor()
        cur.execute("USE charging_db;")
        cur.execute("SELECT * FROM questions;")
        questions = cur.fetchone()
        st.session_state.questions = questions
        question_id, question, standard_answer = questions
        st.write(f"发布的题目：{question}")
        # 检查是否已经提交过答案
        cur = con.cursor()
        cur.execute("USE charging_db;")
        cur.execute("SELECT * FROM answers WHERE student_name = '%s' AND question_id = %d;"
                % (st.session_state.student_name, question_id))
        if cur.rowcount > 0:
            st.error("您已经提交过答案！")
        else:
            if st.button("开始答题"):
                st.session_state.stage = 7
elif st.session_state.stage == 7:
    # 学生端回答题目
    st.sidebar.image("项目2-大模型应用创意设计/figures/image2.jpg")
    if st.button("返回主页"):
        st.session_state.stage = 0
    student = Student(st.session_state.student_name)
    question_id, question, standard_answer = st.session_state.questions
    st.write("当前登陆用户：", st.session_state.student_name)
    st.write(f"问题 {question_id}：{question}")
    answer = st.text_input("请输入你的答案")
    if st.button("提交答案"):
        st.success("答案已提交！")
        student.submit_answer(answer, question_id, standard_answer, question)
        st.success("反馈已生成！")
        feedback = student.query_feedback(question_id)
        question_id, score, feedback = feedback
        st.write(f"问题 {question_id} 的反馈：")
        st.write(f"得分：{score}")
        st.write(f"反馈：{feedback}")