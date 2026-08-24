# Step 12: Responsive Design & Dark Mode

Streamlit provides built-in support for responsive design and dark mode. This document covers what's already working and how to test it.

## Dark Mode (Built-in)

Streamlit automatically respects the user's system theme preference and supports manual toggling.

### How it works:
- Users can toggle dark/light mode in Settings (⚙️ menu, top right)
- CSS automatically adapts colors and contrast
- All charts (Plotly, Folium) adapt to theme automatically

### What we did:
- Color tokens are defined in `src/ui/config.py` as hex values
- Charts use Plotly default theme (adapts automatically)
- Tables and metrics use Streamlit's built-in styling (adapts automatically)

### To test dark mode:
1. Run `streamlit run app.py`
2. Click ⚙️ (Settings) in top right
3. Toggle "Dark" under Theme
4. Verify: colors adapt, text remains readable, charts are visible

**Current state:** ✅ Works automatically, no code changes needed.

---

## Responsive Design

Streamlit's layout system is responsive by default using flexbox and CSS grid.

### How it works:
- `st.columns()` adapts to screen width automatically
- Wide content (maps, tables, charts) use `use_container_width=True`
- Text wraps naturally at smaller widths
- Mobile-optimized padding and margins

### What we're using:
- `st.columns()` for side-by-side layouts (metrics, charts)
- `st.expander()` for collapsible content (reduces mobile clutter)
- `st.dataframe()` with `use_container_width=True` for tables
- `st.plotly_chart()` with `use_container_width=True` for charts

### To test responsive design:

**On Desktop (1920x1080):**
```bash
streamlit run app.py
# Verify: 2-column layouts display side-by-side, charts are wide
```

**On Tablet (768x1024):**
- Open DevTools (F12)
- Click toggle device toolbar (Ctrl+Shift+M)
- Select iPad or similar
- Verify: layouts stack vertically, maps/tables scroll horizontally

**On Mobile (375x667):**
- DevTools: select iPhone or similar
- Verify: all content is readable, no horizontal scroll of page body
- KPI metrics stack vertically
- Chat input works smoothly

### Known limitations:
- Map (Folium) on very small screens may be cramped (accepted MVP limitation)
- Very wide tables may need horizontal scroll (expected behavior)

**Current state:** ✅ Works automatically, minimal code changes needed.

---

## Testing Checklist

- [ ] **Dark Mode:** Toggle Settings → Theme → Dark, verify all pages adapt
- [ ] **Light Mode:** Toggle Settings → Theme → Light, verify contrast is good
- [ ] **Desktop (1920x1080):** Multi-column layouts display side-by-side
- [ ] **Tablet (768x1024):** Layouts stack vertically, content readable
- [ ] **Mobile (375x667):** All content visible, page doesn't scroll horizontally
- [ ] **Charts:** Visible and readable in both themes
- [ ] **Tables:** Scrollable but readable, no horizontal page scroll
- [ ] **Map:** Visible (may be cramped on mobile, acceptable)

---

## Optional Enhancements (Not in MVP)

These are improvements that could be made but are beyond Step 12 scope:

- Add custom CSS for mobile-specific padding adjustments
- Implement responsive map sizing (reduce zoom on mobile)
- Add swipe gestures for navigation
- Optimize table column width on mobile

**For now:** Streamlit's defaults are sufficient for MVP. If users report issues, revisit this.

---

## Reference

- Streamlit Docs: https://docs.streamlit.io/library/api-reference/layout
- Responsive Testing: DevTools Device Toolbar (F12 → Ctrl+Shift+M)
- Theme API: Settings (⚙️) built into Streamlit
