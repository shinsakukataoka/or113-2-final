import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import TABLEAU_COLORS
import textwrap, io

# ── sample CSV text ───────────────────────────────────────────────
csv_text = textwrap.dedent("""\
day,shift,course,task
22,3,MATH4008,Quiz 2
22,4,IM2010,Homework 1
22,10,MGT1002,Quiz
22,14,IM3004,Case Study Presentation
23,3,IM3004,Case Study Presentation
23,4,MATH4008,Quiz 2
23,11,IM3004,Case Study Presentation
24,2,CSIE1212,Homework 1
24,3,IM2010,Homework 1
24,4,MATH4008,Quiz 2
24,14,IM2010,Homework 1
25,2,CSIE1212,Homework 1
25,4,ECON1023,Quiz 2
25,7,MGT1002,Exam 1
25,16,IM2010,Homework 1
26,3,CSIE1212,Homework 0
26,4,ECON1023,Quiz 1
26,5,MATH4008,Worksheet 2
26,8,IM3004,Case Study Presentation
28,1,CSIE1212,Homework 1
28,4,MGT1002,Exam 1
""")

csv_text_2 = textwrap.dedent("""\
day,shift,course,task
22,10,MGT1002,Quiz
23,1,IM3004,Case Study Presentation
23,2,MATH4008,Quiz 2
23,5,IM2010,Homework 1
23,7,CSIE1212,Mini HW C
24,1,IM3004,Case Study Presentation
24,2,MATH4008,Quiz 2
24,5,MGT1002,Exam 1
25,1,IM3004,Case Study Presentation
25,2,MATH4008,Worksheet 2
25,5,IM2010,Homework 1
25,7,CSIE1212,Mini HW C
26,3,CSIE1212,Homework 1
26,4,ECON1023,Quiz 1
27,4,ECON1023,Quiz 3
27,6,CSIE1212,Homework 1
28,4,ECON1023,Quiz 3
28,6,CSIE1212,Homework 1
""")

df = pd.read_csv(io.StringIO(csv_text_2))

# ── task category to single letter ─────────────────────────────────
def categorize_letter(task: str) -> str:
    t = task.lower()
    if any(x in t for x in ['exam', 'midterm', 'final', 'quiz']):
        return 'E'
    if any(x in t for x in ['homework', 'hw', 'webwork', 'worksheet', 'survey', 'case']):
        return 'H'
    return 'L'

df['cat_letter'] = df['task'].apply(categorize_letter)

# ── dynamic day span; fixed shift span 1–16 ───────────────────────
day_min, day_max = df['day'].min(), df['day'].max()
days_range       = range(day_min, day_max + 1)
shifts_range     = range(1, 17)           # **always 16 shifts**

# ── colour map for courses ────────────────────────────────────────
unique_courses = sorted(df['course'].unique())
palette = list(TABLEAU_COLORS.values())
while len(palette) < len(unique_courses):
    palette += palette
course_colors = {c: palette[i] for i, c in enumerate(unique_courses)}

# ── plot ──────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 6))

for day in days_range:
    for shift in shifts_range:
        rows = df[(df['day'] == day) & (df['shift'] == shift)]
        if not rows.empty:
            row    = rows.iloc[0]
            color  = course_colors[row['course']]
            letter = row['cat_letter']
        else:
            color, letter = 'white', ''
        rect = mpatches.Rectangle((shift - 1, day - day_min), 1, 1,
                                  facecolor=color, edgecolor='grey',
                                  linewidth=0.5)
        ax.add_patch(rect)
        if letter:
            ax.text(shift - 0.5, day - day_min + 0.5, letter,
                    ha='center', va='center',
                    fontsize=10, fontweight='bold')

# ── axes & titles ─────────────────────────────────────────────────
ax.set_xlim(0, 16)
ax.set_ylim(0, day_max - day_min + 1)

ax.set_xticks(np.arange(0.5, 16.5))
ax.set_xticklabels(range(1, 17))
ax.set_xlabel('Shift (1–16)')

ax.set_yticks(np.arange(0.5, day_max - day_min + 1.5))
ax.set_yticklabels(range(day_min, day_max + 1))
ax.set_ylabel('Day')

ax.set_title(f'Course Schedule (Days {day_min}–{day_max})\n')
ax.invert_yaxis()
ax.set_aspect('equal')
ax.grid(True, which='both', color='lightgrey',
        linewidth=0.3, linestyle='--')

# ── legends ───────────────────────────────────────────────────────
course_patches = [mpatches.Patch(color=course_colors[c], label=c)
                  for c in unique_courses]
cat_patches = [
    mpatches.Patch(facecolor='white', edgecolor='black', label='L Lecture'),
    mpatches.Patch(facecolor='white', edgecolor='black', label='H Homework'),
    mpatches.Patch(facecolor='white', edgecolor='black', label='E Exam/Quiz (incl. preperation)')
]

leg1 = ax.legend(handles=course_patches, title='Course',
                 loc='upper left', bbox_to_anchor=(1.02, 1))
leg2 = ax.legend(handles=cat_patches, title='Letter Key',
                 loc='upper left', bbox_to_anchor=(1.02, 0.36),
                 framealpha=0)
ax.add_artist(leg1)

plt.tight_layout()
plt.show()