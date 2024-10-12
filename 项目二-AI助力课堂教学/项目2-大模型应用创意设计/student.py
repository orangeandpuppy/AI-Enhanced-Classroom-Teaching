from util import connect_db, get_feedback


class Student:
    def __init__(self, student_name):
        self.student_name = student_name

    def submit_answer(self, answer, question_id, standard_answer, question):
        # 输入答案
        with connect_db() as con:
            cur = con.cursor()
            cur.execute("USE charging_db;")
            cur.execute("INSERT INTO answers VALUES ('%s', '%s', %d);" % (self.student_name, answer, question_id))
            con.commit()
            print("答案已提交！\n")

        # 将学生的答案传递给大语言模型，获取反馈
        score, feedback = get_feedback(self.student_name, answer, standard_answer, question_id, question)
        print(f"得分：{score}")
        print(f"反馈：{feedback}")

        return question_id

    # 查询反馈
    def query_feedback(self, question_id):
        with connect_db() as con:
            cur = con.cursor()
            cur.execute("USE charging_db;")
            cur.execute("SELECT * FROM feedbacks WHERE student_name = '%s' AND question_id = %d;" % (self.student_name, question_id))
            if cur.rowcount == 0:
                print(f"暂无问题 {question_id} 的反馈！")
                return []
            else:
                feedback = cur.fetchone()
                print(f"问题 {question_id} 的反馈：")
                print(f"得分：{feedback[1]}")
                print(f"反馈：{feedback[2]}")
                print("\n")
                return [question_id, feedback[1], feedback[2]]


def in_db(student_name):
    with connect_db() as con:
        cur = con.cursor()
        cur.execute("USE charging_db;")
        cur.execute("SELECT * FROM students WHERE name = '%s';" % (student_name,))
        return cur.fetchone() is not None


if __name__ == '__main__':
    # 检查数据库是否存在
    with connect_db() as con:
        cur = con.cursor()
        if cur.execute("SHOW DATABASES LIKE 'charging_db';") == 0:
            raise Exception("数据库不存在！")

    # 输入学生姓名
    student_name = input("请输入学生姓名：")
    while not in_db(student_name):
        student_name = input("学生姓名不存在，请重新输入：")
    print("成功登陆！\n")

    student = Student(student_name)
    question_id = student.query_feedback(11)

