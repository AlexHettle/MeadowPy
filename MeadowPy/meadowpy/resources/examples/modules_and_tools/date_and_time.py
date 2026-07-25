# Date & Time
# The datetime module handles dates, times, and durations.

from datetime import datetime, date, timedelta

# === Current date and time ===
now = datetime.now()
print(f"Right now: {now}")
print(f"Date only: {now.date()}")
print(f"Time only: {now.time()}")

# === Formatting dates ===
print(f"\nFormatted: {now.strftime('%B %d, %Y')}")  # March 15, 2024
print(f"Short:     {now.strftime('%m/%d/%y')}")     # 03/15/24
print(f"ISO:       {now.isoformat()}")

# === Creating specific dates ===
birthday = date(2000, 6, 15)
print(f"\nBirthday: {birthday}")
print(f"Day of week: {birthday.strftime('%A')}")

# === Date arithmetic with timedelta ===
today = date.today()
one_week = timedelta(weeks=1)
thirty_days = timedelta(days=30)

print(f"\nToday: {today}")
print(f"Next week: {today + one_week}")
print(f"30 days ago: {today - thirty_days}")

# === Difference between dates ===
new_year = date(today.year + 1, 1, 1)
days_left = (new_year - today).days
print(f"\nDays until New Year: {days_left}")

# === Parsing a date from a string ===
date_str = "2024-03-15 14:30:00"
parsed = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
print(f"\nParsed: {parsed}")
print(f"Hour: {parsed.hour}, Minute: {parsed.minute}")
