class Person:
    def __init__(self, name: str, birth_year: int):
        self.name = name
        self.birth_year = birth_year

    def age(self, current_year: int) -> int:
        return current_year - self.birth_year

class Student(Person):
    def __init__(self, name: str, birth_year: int, student_id: str):
        super().__init__(name, birth_year)
        self.student_id = student_id
        self.enrollments: list[Enrollment] = []

    def enroll(self, course: Course) -> Enrollment:
        enrollment = Enrollment(self, course)
        self.enrollments.append(enrollment)
        return enrollment

class Course:
    def __init__(self, code: str, title: str, credits: int):
        self.code = code
        self.title = title
        self.credits = credits

class Enrollment:
    def __init__(self, student: Student, course: Course):
        self.student = student
        self.course = course
        self.grade: str | None = None
