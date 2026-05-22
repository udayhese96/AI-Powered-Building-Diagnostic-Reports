"""
chart_generator.py - Generates a modern flat-design pie chart for checklist severity.
"""

import os
import matplotlib
matplotlib.use('Agg')  # use non-interactive backend
import matplotlib.pyplot as plt

def generate_severity_chart(checklist_items: dict, output_path: str) -> bool:
    """
    Counts checklist ratings and generates a clean, modern pie chart saved as PNG.
    """
    try:
        # Flatten all checklists
        wc = checklist_items.get("wc_checklist", {})
        ext = checklist_items.get("external_wall_checklist", {})
        
        # Combine
        all_items = {**wc, **ext}
        
        # Define mapping
        # Positive / Good
        good_vals = {"good", "yes", "100%", "75%", "all time"}
        # Neutral / Moderate
        mod_vals = {"moderate", "not sure", "n/a"}
        # Negative / Poor
        poor_vals = {"poor", "no"}
        
        counts = {"Good": 0, "Moderate": 0, "Poor": 0}
        
        for q, val in all_items.items():
            v_lower = str(val).strip().lower()
            if any(x in v_lower for x in good_vals):
                counts["Good"] += 1
            elif any(x in v_lower for x in mod_vals):
                counts["Moderate"] += 1
            elif any(x in v_lower for x in poor_vals):
                counts["Poor"] += 1
            else:
                counts["Good"] += 1  # default fallback
                
        # If no items, make a dummy chart
        total = sum(counts.values())
        if total == 0:
            counts = {"Good": 1, "Moderate": 0, "Poor": 0}
            
        labels = []
        sizes = []
        colors = []
        
        # We only plot categories that have > 0 counts
        color_map = {
            "Good": "#2E5299",      # Sleek Blue
            "Moderate": "#E07B39",  # Corporate Orange
            "Poor": "#C00000"       # Deep Muted Red
        }
        
        for cat, cnt in counts.items():
            if cnt > 0:
                labels.append(f"{cat} ({cnt})")
                sizes.append(cnt)
                colors.append(color_map[cat])
                
        # Plot
        fig, ax = plt.subplots(figsize=(6, 4.5), dpi=300)
        
        wedges, texts, autotexts = ax.pie(
            sizes, 
            labels=labels, 
            autopct='%1.1f%%',
            startangle=140, 
            colors=colors,
            textprops=dict(color="black", weight="bold", size=10),
            wedgeprops=dict(width=0.6, edgecolor='white', linewidth=2)  # Donut style
        )
        
        # Style autopct text
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_size(10)
            
        ax.set_title("Checklist Severity Distribution", fontsize=14, pad=20, weight="bold", color="#1F3864")
        
        # Clean background and display
        plt.tight_layout()
        
        # Ensure directory exists
        dir_name = os.path.dirname(output_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        plt.savefig(output_path, bbox_inches='tight', transparent=True)
        plt.close(fig)
        return True
        
    except Exception as e:
        print(f"Failed to generate severity chart: {e}")
        return False
