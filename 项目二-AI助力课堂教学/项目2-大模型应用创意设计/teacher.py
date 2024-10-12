from config import config
from util import connect_db, get_standard_answer, get_overall_situation
from wordcloud import WordCloud
import matplotlib.pyplot as plt


class Teacher:
    def __init__(self):
        pass

    def publish_question(self, question: str, question_id: int):
        """
            发布题目
        """
        standard_answer = get_standard_answer(question)

        # 发布题目
        with connect_db() as con:
            cur = con.cursor()
            cur.execute("USE charging_db;")
            cur.execute("INSERT INTO questions (question_id, question, standard_answer) VALUES (%d , '%s', '%s');"
                        % (question_id, question, standard_answer))
            con.commit()
            print(f"题目 {question} 发布成功！")

    def view_current_situation(self):
        """
            查看目前答题情况
        """
        with connect_db() as con:
            cur = con.cursor()
            cur.execute("USE charging_db;")
            cur.execute("SELECT * FROM questions;")
            if cur.rowcount == 0:
                print("暂无题目正在答题！")
                return []
            else:
                question = cur.fetchone()
                question_id = question[0]
                question = question[1]
                print(f"当前正在答题的题目：{question_id}. {question}")
                # 统计学生总数
                cur.execute("SELECT * FROM students;")
                student_count = cur.rowcount
                # 统计已经提交答案的学生人数
                cur.execute("SELECT * FROM answers WHERE question_id = %d;" % question_id)
                answered_count = cur.rowcount
                print(f"该题目已有 {answered_count} 人提交答案，共 {student_count} 人。")
                return [question_id, question, student_count, answered_count]

    def stop_answer(self, question_id: int, question: str, standard_answer: str):
        """
            终止答题
        """
        get_overall_situation(question_id, question, standard_answer)
        return question_id


if __name__ == '__main__':
    print("\n\n欢迎使用教师端\n")
    teacher = Teacher()