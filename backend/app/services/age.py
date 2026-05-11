from datetime import date


def calculate_age_on(birth_date: date, on_date: date) -> int:
    age = on_date.year - birth_date.year
    if (on_date.month, on_date.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def calculate_age_by_birth_year(birth_date: date, on_date: date) -> int:
    return on_date.year - birth_date.year


def calculate_event_age(birth_date: date, on_date: date, is_republic_championship: bool = False) -> int:
    if is_republic_championship:
        return calculate_age_by_birth_year(birth_date, on_date)
    return calculate_age_on(birth_date, on_date)
