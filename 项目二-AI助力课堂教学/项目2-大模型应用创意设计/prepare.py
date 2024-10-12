from util import connect_db, init_db, load_pdf
from config import config

def prepare():
    # 获取学生信息，并将其存入数据库
    students_path = config['student_name']
    student_name = []
    with open(students_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        student_name = [line.strip() for line in lines]
    with connect_db() as con:
        cur = con.cursor()
        # 判断数据库charging_db是否存在，不存在则创建
        if cur.execute("SHOW DATABASES LIKE 'charging_db';") == 0:
            init_db(con)
            cur.execute("USE charging_db;")
            cur.execute("UPDATE class SET student_count = %d WHERE class_id = 1;" % (len(student_name),))
            for name in student_name:
                cur.execute("INSERT INTO students VALUES ('%s');" % (name,))
            con.commit()
        print("班级学生已存入数据库！")

    # 加载PDF文档
    with connect_db() as con:
        cur = con.cursor()
        cur.execute("USE charging_db;")
        cur.execute("SELECT len FROM pdflen WHERE id = 1;")
        len = cur.fetchone()[0]
        print("数据库中已有文档长度：", len)
        if len == 0:
            load_pdf()
            print("PDF文档已加载！")
        else:
            print("PDF文档已加载！")

    # 重置数据库环境
    with connect_db() as con:
        cur = con.cursor()
        cur.execute("USE charging_db;")
        cur.execute("DELETE FROM questions;")
        cur.execute("DELETE FROM answers where student_name = '张三';")
        cur.execute("DELETE FROM feedbacks where student_name = '张三';")
        con.commit()

if __name__ == '__main__':
    prepare()