from util import connect_db, get_feedback
from config import config
from faker import Faker

def add_answer(student_name, answer, question_id, question, standard_answer):
    with connect_db() as con:
        cur = con.cursor()
        cur.execute("USE charging_db;")
        cur.execute("INSERT INTO students VALUES ('%s');" % (student_name,))
        cur.execute("INSERT INTO answers VALUES ('%s', '%s', %d);" % (student_name, answer, question_id))
        con.commit()
        print("答案已提交！\n")

    # 将学生的答案传递给大语言模型，获取反馈
    get_feedback(student_name, answer, standard_answer, question_id, question)


if __name__ == '__main__':
    # 重置数据库环境
    with connect_db() as con:
        cur = con.cursor()
        cur.execute("USE charging_db;")
        cur.execute("INSERT INTO questions VALUES (1, '中庸之道是什么', '中庸之道是中国古代儒家文化中的重要概念1。它强调的是“中正平和”的处事态度和生活方式。;')")
        con.commit()



