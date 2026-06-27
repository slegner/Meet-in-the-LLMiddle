import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

NAVY="#0b1b3a"; PANEL="#16315f"; GOLD="#f2c14e"; INK="#eaf0fb"
BLUE="#2f7bf6"; GREEN="#5fc27e"; PINK="#e066a6"; MUT="#9fb3d6"

fig, ax = plt.subplots(figsize=(14, 9))
fig.patch.set_facecolor(NAVY); ax.set_facecolor(NAVY)
ax.set_xlim(0, 14); ax.set_ylim(0, 9); ax.axis("off")

def box(x, y, w, h, title, sub="", fc=PANEL, ec=GOLD, tc=INK, fs=12):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.12",
                                fc=fc, ec=ec, lw=2))
    ax.text(x+w/2, y+h/2+(0.16 if sub else 0), title, ha="center", va="center",
            color=tc, fontsize=fs, fontweight="bold")
    if sub:
        ax.text(x+w/2, y+h/2-0.28, sub, ha="center", va="center", color=MUT, fontsize=8.7)

def arrow(x1, y1, x2, y2, color=GOLD, style="-|>", lw=2.2, ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=18,
                                 color=color, lw=lw, ls=ls,
                                 connectionstyle=f"arc3,rad={rad}"))

ax.text(7, 8.62, "LEGAL DOJO — ADK Agent Team (one negotiation turn)",
        ha="center", color=GOLD, fontsize=16, fontweight="bold")

# Inputs (left column)
box(0.3, 6.7, 3.0, 0.95, "Your message", "the student's argument", fc="#13284f", ec=BLUE)
box(0.3, 4.9, 3.0, 1.1, "Concession Rules", "deterministic: aggressive -> concede\non strong arg -> compromise (turn 6-12)", fc="#13284f", ec=GREEN, fs=11)

# Shared session state band
ax.add_patch(FancyBboxPatch((4.0, 3.55), 8.2, 0.0+ 0.0, boxstyle="round", fc=PANEL, ec=PANEL))
box(4.0, 3.5, 8.2, 0.7, "SHARED SESSION STATE  (every agent reads & writes here)", "", fc="#0f244c", ec=MUT, tc=MUT, fs=10)

# Reply chain (sequential) — top row
box(4.0, 5.7, 2.4, 1.2, "1 · Director", "picks tactic +\ninstruction", fc=PANEL, ec=GOLD, fs=11.5)
box(6.9, 5.7, 2.5, 1.2, "2 · Adversary", "writes 3 candidate\nreplies", fc=PANEL, ec=GOLD, fs=11.5)
box(9.9, 5.7, 2.4, 1.2, "3 · Predictor", "forecasts each,\npicks the best", fc=PANEL, ec=GOLD, fs=11.5)

# NoteTaker (parallel) — bottom
box(6.9, 1.9, 2.5, 1.1, "NoteTaker", "private read of you\n(confidence, trust, tells)", fc="#2a1840", ec=PINK, fs=11.5)
ax.text(8.15, 3.18, "runs in PARALLEL", ha="center", color=PINK, fontsize=9, style="italic")

# Outputs (right)
box(12.5, 5.75, 1.4, 1.1, "Reply", "to you", fc="#13284f", ec=BLUE, fs=11)
box(10.2, 0.35, 3.7, 1.0, "MEMORY (persists)", "transcript + per-turn private notes\nfed back into every future turn",
    fc="#102a1c", ec=GREEN, fs=10.5)

# Arrows: inputs -> agents
arrow(3.3, 7.15, 5.2, 6.9, color=BLUE)            # message -> director
arrow(3.3, 6.95, 8.0, 3.0, color=BLUE, rad=-0.15) # message -> notetaker
arrow(3.3, 5.45, 5.2, 5.7, color=GREEN)           # rules -> director

# Reply chain sequential arrows
arrow(6.4, 6.3, 6.9, 6.3, color=GOLD)             # director -> adversary
arrow(9.4, 6.3, 9.9, 6.3, color=GOLD)             # adversary -> predictor
arrow(12.3, 6.3, 12.5, 6.3, color=GOLD)           # predictor -> reply

# State read/write (dashed)
for cx in (5.2, 8.15, 11.1):
    arrow(cx, 5.7, cx, 4.2, color=MUT, lw=1.4, ls=(0,(4,3)), style="<|-|>")
arrow(8.15, 1.9, 8.15, 4.2, color=MUT, lw=1.4, ls=(0,(4,3)), style="<|-|>")

# Outputs to memory + feedback loop
arrow(8.15, 1.9, 10.6, 1.35, color=PINK, rad=-0.2)   # note -> memory
arrow(13.2, 5.75, 13.2, 1.35, color=BLUE, rad=0.0)   # reply -> memory (transcript)
arrow(10.2, 0.85, 1.8, 0.85, color=GREEN, lw=2, rad=0.0)  # memory feedback
arrow(1.8, 0.85, 1.8, 4.9, color=GREEN, lw=2, ls=(0,(5,3)))
ax.text(5.9, 0.6, "memory feeds the next turn", ha="center", color=GREEN, fontsize=9, style="italic")

# Legend
ax.text(0.3, 8.05, "gold = reply chain (sequential)   pink = parallel note   green = memory loop",
        color=MUT, fontsize=9)

plt.tight_layout()
out="/Users/starfish/Desktop/PhD2025-26/LLMiddle/legal-dojo/docs/adk_architecture.png"
import os; os.makedirs(os.path.dirname(out), exist_ok=True)
plt.savefig(out, dpi=150, facecolor=NAVY, bbox_inches="tight")
print("saved", out)
