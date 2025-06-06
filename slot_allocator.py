
def assign_slots(students, max_per_slot=5, start_slot=1):
    slots = {}
    current_slot = start_slot
    for student in students:
        if current_slot not in slots:
            slots[current_slot] = []
        if len(slots[current_slot]) >= max_per_slot:
            current_slot += 1
            slots[current_slot] = []
        slots[current_slot].append(student)
    return slots
