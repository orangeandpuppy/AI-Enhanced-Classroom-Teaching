import os
import openai
from langchain_openai import ChatOpenAI
from config import config
import pymysql as py
from langchain_community.document_loaders import PyMuPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import ChatPromptTemplate
import json
from collections import Counter
from matplotlib import pyplot as plt

os.environ['OPENAI_API_BASE'] = config['OPENAI_API_BASE']
os.environ['OPENAI_API_KEY'] = config['OPENAI_API_KEY']
openai.api_base = os.environ["OPENAI_API_BASE"]
openai.api_key = os.environ["OPENAI_API_KEY"]


def get_chat(temperature: float = 0.1):
    # 初始化一个 Chat 对象
    chat = ChatOpenAI(temperature=temperature)
    return chat


def connect_db():
    # 连接数据库
    conn = py.connect(host=config['host'],
                      user=config['user'],
                      password=config['password'],
                      port=config['port'],
                      charset=config['charset'])
    return conn


def init_db(con):
    # 初始化数据库
    cur = con.cursor()
    cur.execute("CREATE DATABASE charging_db;")
    cur.execute("USE charging_db;")
    # 学生名单(预先录入)
    cur.execute("CREATE TABLE students (name VARCHAR(20) PRIMARY KEY);")
    # 班级人数
    cur.execute("CREATE TABLE class (class_id INT PRIMARY KEY, student_count INT);")
    cur.execute("INSERT INTO class VALUES (1, 0);")
    # 文档长度
    cur.execute("CREATE TABLE pdflen (id INT PRIMARY KEY, len INT);")
    cur.execute("INSERT INTO pdflen VALUES (1, 0);")
    # 题目(同一时间只能发布一道题目
    cur.execute("CREATE TABLE questions ("
                "question_id        INT PRIMARY KEY, "
                "question           VARCHAR(100), "
                "standard_answer    VARCHAR(400));")
    # 学生答案
    cur.execute("CREATE TABLE answers ("
                "student_name       VARCHAR(20), "
                "answer             VARCHAR(400), "
                "question_id        INT, "
                "FOREIGN KEY (student_name) REFERENCES students(name));")
    # 大语言模型反馈
    cur.execute("CREATE TABLE feedbacks ("
                "`student_name`     VARCHAR(20), "
                "`score`            INT, "
                "`feedback`         VARCHAR(400), "
                "`keywords1`        VARCHAR(60), "
                "`keywords2`        VARCHAR(60), "
                "`keywords3`        VARCHAR(60), "
                "`question_id`      INT, "
                "FOREIGN KEY (student_name) REFERENCES students(name));")
    # 答题总体情况
    cur.execute("CREATE TABLE overall_situations ("
                "question_id        INT PRIMARY KEY, "
                "keywords_freq      VARCHAR(4000), "
                "analysis           VARCHAR(1000));")
    con.commit()


def load_pdf():
    # 从文件夹中加载PDF文档
    file_dir = config['file_dir']
    pdf_files = [os.path.join(file_dir, file) for file in os.listdir(file_dir) if file.endswith('.pdf')]
    loaders_chinese = [PyMuPDFLoader(file) for file in pdf_files]

    # 分割文档
    docs = []
    for loader in loaders_chinese:
        docs.extend(loader.load())
    text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=10)
    documents = text_splitter.split_documents(docs)
    with connect_db() as con:
        cur = con.cursor()
        cur.execute("USE charging_db;")
        print("文档长度：", len(documents))
        cur.execute("UPDATE pdflen SET len = %d WHERE id = 1;" % (len(documents),))
        con.commit()

    # 向量化文档并存储
    db = Chroma.from_documents(documents, embedding=OpenAIEmbeddings(), persist_directory=config['save_embeddings_dir'])
    db.persist()


def get_standard_answer(question: str):
    # 获取标准答案
    chat = get_chat()
    chain = load_qa_chain(chat, chain_type="stuff")
    db = Chroma(persist_directory=config['save_embeddings_dir'], embedding_function=OpenAIEmbeddings())

    sim_docs = db.similarity_search(question, 5)
    standard_answer = chain.run(input_documents=sim_docs, question=question)
    return standard_answer


def get_feedback(student_name: str, answer: str, standard_answer: str, question_id: int, question: str):
    # 获取反馈
    chat = get_chat(temperature=0.0)
    task = ["用0-100分给学生答案打分，打分时请比较学生答案与标准答案的相似度，并考虑学生答案的完整性（40分）、准确性（30分）、清晰度（30分）等因素，仅输出评分。",
            "写一段150字以内的反馈，指出学生答案的优点和不足之处。", "用三个关键词概括学生答案内容，关键词之间用逗号```,```间隔。", ]
    template_string = """
    你将获得以下数据：
    - 问题题干：{question}
    - 标准答案：{standard_answer}
    - 学生答案：{answer}
    请{task}
    """
    feedback = list()
    for i in range(3):
        prompt_template = ChatPromptTemplate.from_template(template_string)
        prompt = prompt_template.format_messages(question=question, standard_answer=standard_answer, answer=answer,
                                                 task=task[i])
        feedback.append(chat(prompt).content)
    keywords = feedback[2].split(",")

    with connect_db() as con:
        cur = con.cursor()
        cur.execute("USE charging_db;")
        cur.execute("INSERT INTO feedbacks VALUES ('%s', %d, '%s', '%s', '%s', '%s', %d);" % (
            student_name, int(feedback[0]), feedback[1], keywords[0], keywords[1], keywords[2], question_id))
        con.commit()

    return int(feedback[0]), str(feedback[1])


def get_overall_situation(question_id: int, question: str, standard_answer: str):
    # 获取全部关键词
    keywords = list()
    with connect_db() as con:
        cur = con.cursor()
        cur.execute("USE charging_db;")
        cur.execute("SELECT keywords1, keywords2, keywords3 FROM feedbacks WHERE question_id = %d;" % question_id)
        for feedback in cur.fetchall():
            keywords.extend(feedback)
    keywords_count = len(keywords)
    keywords_freq = ""
    words_freq = Counter(keywords)
    for word, freq in words_freq.items():
        keywords_freq += f"{word}:{freq / keywords_count},"

    chat = get_chat(temperature=0.0)
    # 获取学生总体答题情况
    template_string = """
        你将获得各由三个引号括起来的问题题干、标准答案、学生总体答案中关键词频率，
        请根据关键词频率和标准答案，用200字左右分析学生总体答题情况，指出学生普遍存在的问题和优点。
        问题题干
        ```{question}```
        标准答案
        ```{standard_answer}```
        学生总体答案中关键词频率
        ```{keywords_freq}```
        """
    prompt_template = ChatPromptTemplate.from_template(template_string)
    prompt = prompt_template.format_messages(question=question, standard_answer=standard_answer,
                                             keywords_freq=keywords_freq)
    analysis = chat(prompt)
    analysis = analysis.content

    # 获取关键词频率
    template_string = """
        你将获得以下数据：
        - 问题题干：{question}
        - 标准答案：{standard_answer}
        - 学生总体答案中关键词频率：{keywords_freq}

        请执行以下任务：
        1. 重新统计关键词出现的频率，合并具有相似意思的关键词，按照频率从高到低排序。
        2. 输出格式为 ```关键词1:频率1,关键词2:频率2,关键词3:频率3```，每一组关键词和频率之间用逗号```,```间隔，
        关键词和频率之间用冒号```:```间隔，最多输出50组关键词和频率。
        """
    prompt_template = ChatPromptTemplate.from_template(template_string)
    prompt = prompt_template.format_messages(question=question, standard_answer=standard_answer,
                                             keywords_freq=keywords_freq)
    words_freq = chat(prompt)
    words_freq = words_freq.content
    words_freq = words_freq.replace("\n", "").replace("\r", "").replace(" ", "")
    words_freq = words_freq.split(",")
    keywords_freq = ""
    count = 0
    l = min(min(len(words), len(freqs)), 50)
    for i in range(l):
        keywords_freq += f"{words[i]}:{freqs[i]}"
        if i != l - 1:
            keywords_freq += ","
    for word_freq in words_freq:
        word, freq = word_freq.split(":")
        keywords_freq += f"{word}:{freq}"
        count = count + 1
        if word != len(word_freq) - 1 and count != 50:
            keywords_freq += ","
        if count == 50:
            break

    # 保存总体答题情况
    with connect_db() as con:
        cur = con.cursor()
        cur.execute("USE charging_db;")
        cur.execute("DELETE FROM overall_situations WHERE question_id = %d;" % question_id)
        cur.execute("INSERT INTO overall_situations VALUES (%d, '%s', '%s');" % (
            question_id, keywords_freq, analysis))
        con.commit()
    print("已生成题目", question_id, "的总体答题情况！")


if __name__ == '__main__':
    get_overall_situation(11, '描述“先天下之忧而忧，后天下之乐而乐”的意义。',
                          '这句话体现了一种深厚的社会责任感和无私奉献的精神。')