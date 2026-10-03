/* SPDX-License-Identifier: MIT */
#include "bench_native.h"
#include <ctype.h>
#include <math.h>
#include <png.h>
#include <stdlib.h>
#include <string.h>

/* One drawing path writes both formats. Each panel has its own zero baseline.
 */
typedef struct {
  FILE *svg;
  unsigned char *pixels;
  int width, height;
} canvas;
static const unsigned colors[] = {0x1769aa, 0xb34b17, 0x21805b};
static void pixel(canvas *c, int x, int y, unsigned rgb) {
  if (x < 0 || y < 0 || x >= c->width || y >= c->height)
    return;
  unsigned char *p = c->pixels + 3 * ((size_t)y * c->width + x);
  p[0] = (unsigned char)(rgb >> 16);
  p[1] = (unsigned char)(rgb >> 8);
  p[2] = (unsigned char)rgb;
}
static void line(canvas *c, int x, int y, int xx, int yy, unsigned color) {
  fprintf(c->svg,
          "<path d=\"M%d %dL%d %d\" fill=\"none\" stroke=\"#%06x\" "
          "stroke-width=\"2\"/>\n",
          x, y, xx, yy, color);
  int dx = abs(xx - x), sx = x < xx ? 1 : -1, dy = -abs(yy - y),
      sy = y < yy ? 1 : -1, err = dx + dy;
  for (;;) {
    pixel(c, x, y, color);
    pixel(c, x + 1, y, color);
    if (x == xx && y == yy)
      break;
    int e = err * 2;
    if (e >= dy) {
      err += dy;
      x += sx;
    }
    if (e <= dx) {
      err += dx;
      y += sy;
    }
  }
}
/* Original 5x7 display glyphs; no font download or rendering process. */
static const unsigned char glyphs[][7] = {
    {14, 17, 17, 31, 17, 17, 17}, {30, 17, 17, 30, 17, 17, 30},
    {14, 17, 16, 16, 16, 17, 14}, {30, 17, 17, 17, 17, 17, 30},
    {31, 16, 16, 30, 16, 16, 31}, {31, 16, 16, 30, 16, 16, 16},
    {14, 17, 16, 23, 17, 17, 14}, {17, 17, 17, 31, 17, 17, 17},
    {14, 4, 4, 4, 4, 4, 14},      {7, 2, 2, 2, 18, 18, 12},
    {17, 18, 20, 24, 20, 18, 17}, {16, 16, 16, 16, 16, 16, 31},
    {17, 27, 21, 21, 17, 17, 17}, {17, 25, 21, 19, 17, 17, 17},
    {14, 17, 17, 17, 17, 17, 14}, {30, 17, 17, 30, 16, 16, 16},
    {14, 17, 17, 17, 21, 18, 13}, {30, 17, 17, 30, 20, 18, 17},
    {15, 16, 16, 14, 1, 1, 30},   {31, 4, 4, 4, 4, 4, 4},
    {17, 17, 17, 17, 17, 17, 14}, {17, 17, 17, 17, 17, 10, 4},
    {17, 17, 17, 21, 21, 21, 10}, {17, 17, 10, 4, 10, 17, 17},
    {17, 17, 10, 4, 4, 4, 4},     {31, 1, 2, 4, 8, 16, 31},
    {14, 17, 19, 21, 25, 17, 14}, {4, 12, 4, 4, 4, 4, 14},
    {14, 17, 1, 2, 4, 8, 31},     {30, 1, 1, 14, 1, 1, 30},
    {2, 6, 10, 18, 31, 2, 2},     {31, 16, 16, 30, 1, 1, 30},
    {14, 16, 16, 30, 17, 17, 14}, {31, 1, 2, 4, 8, 8, 8},
    {14, 17, 17, 14, 17, 17, 14}, {14, 17, 17, 15, 1, 1, 14},
    {0, 0, 0, 31, 0, 0, 0},       {0, 0, 0, 0, 0, 6, 6},
    {0, 6, 6, 0, 6, 6, 0},        {1, 2, 2, 4, 8, 8, 16},
    {0, 0, 0, 0, 0, 0, 31},       {2, 4, 8, 8, 8, 4, 2},
    {8, 4, 2, 2, 2, 4, 8},        {0, 4, 4, 31, 4, 4, 0},
    {0, 0, 31, 0, 31, 0, 0},      {0, 0, 0, 0, 0, 6, 4},
    {17, 2, 4, 8, 17, 0, 0}};
static void xml(FILE *f, const char *s) {
  for (; *s; s++) {
    switch (*s) {
    case '&':
      fputs("&amp;", f);
      break;
    case '<':
      fputs("&lt;", f);
      break;
    case '>':
      fputs("&gt;", f);
      break;
    case '"':
      fputs("&quot;", f);
      break;
    default:
      if ((unsigned char)*s >= 32)
        fputc(*s, f);
    }
  }
}
static void text_at(canvas *c, int x, int y, const char *text, bool center,
                    int scale, unsigned color) {
  fprintf(c->svg,
          "<text x=\"%d\" y=\"%d\" font-family=\"sans-serif\" font-size=\"%d\" "
          "fill=\"#%06x\" text-anchor=\"%s\">",
          x, y, scale * 8, color, center ? "middle" : "start");
  xml(c->svg, text);
  fputs("</text>\n", c->svg);
  int at = x - (center ? (int)strlen(text) * 6 * scale / 2 : 0);
  const char *special = "-.:/_()+=,%";
  for (const unsigned char *p = (const unsigned char *)text; *p;
       p++, at += 6 * scale) {
    int ch = toupper(*p), idx = -1;
    if (ch >= 'A' && ch <= 'Z')
      idx = ch - 'A';
    else if (ch >= '0' && ch <= '9')
      idx = 26 + ch - '0';
    else {
      const char *v = strchr(special, ch);
      if (v)
        idx = 36 + (int)(v - special);
    }
    if (idx < 0)
      continue;
    for (int row = 0; row < 7; row++)
      for (int col = 0; col < 5; col++)
        if (glyphs[idx][row] & (1u << (4 - col)))
          for (int dy = 0; dy < scale; dy++)
            for (int dx = 0; dx < scale; dx++)
              pixel(c, at + col * scale + dx, y - 7 * scale + row * scale + dy,
                    color);
  }
}
static void dot(canvas *c, int x, int y, unsigned color) {
  fprintf(c->svg, "<circle cx=\"%d\" cy=\"%d\" r=\"4\" fill=\"#%06x\"/>\n", x,
          y, color);
  for (int yy = -4; yy <= 4; yy++)
    for (int xx = -4; xx <= 4; xx++)
      if (xx * xx + yy * yy <= 16)
        pixel(c, x + xx, y + yy, color);
}
static bool png_file(const char *path, canvas *c, nb_error *e) {
  FILE *f = nb_exclusive(path, e);
  if (!f)
    return false;
  png_structp png =
      png_create_write_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
  png_infop info = png ? png_create_info_struct(png) : NULL;
  if (!png || !info) {
    if (png)
      png_destroy_write_struct(&png, NULL);
    fclose(f);
    return nb_fail(e, "PNG allocation failed");
  }
  if (setjmp(png_jmpbuf(png))) {
    png_destroy_write_struct(&png, &info);
    fclose(f);
    return nb_fail(e, "PNG encoding failed");
  }
  png_init_io(png, f);
  png_set_IHDR(png, info, (png_uint_32)c->width, (png_uint_32)c->height, 8,
               PNG_COLOR_TYPE_RGB, PNG_INTERLACE_NONE,
               PNG_COMPRESSION_TYPE_DEFAULT, PNG_FILTER_TYPE_DEFAULT);
  png_write_info(png, info);
  for (int y = 0; y < c->height; y++)
    png_write_row(png, c->pixels + (size_t)y * c->width * 3);
  png_write_end(png, NULL);
  png_destroy_write_struct(&png, &info);
  return fclose(f) == 0 ? true : nb_fail(e, "PNG output failed");
}
bool nb_plot(const char *dir, const char *title, const nb_plot_panel *panels,
             size_t n, nb_error *e) {
  if (!n || n > 8)
    return nb_fail(e, "Invalid graph panel count");
  if (!nb_mkdir(dir, e))
    return false;
  char path[4096];
  if (snprintf(path, sizeof(path), "%s/benchmark.svg", dir) >=
      (int)sizeof(path))
    return nb_fail(e, "Graph path too long");
  canvas c = {.width = 1440, .height = 100 + (int)n * 400};
  c.svg = nb_exclusive(path, e);
  if (!c.svg)
    return false;
  c.pixels = malloc((size_t)c.width * c.height * 3);
  if (!c.pixels) {
    fclose(c.svg);
    return nb_fail(e, "Graph allocation failed");
  }
  memset(c.pixels, 255, (size_t)c.width * c.height * 3);
  fprintf(c.svg,
          "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"%d\" "
          "height=\"%d\" viewBox=\"0 0 %d %d\" role=\"img\"><title>",
          c.width, c.height, c.width, c.height);
  xml(c.svg, title);
  fputs("</title><rect width=\"100%\" height=\"100%\" fill=\"white\"/>\n",
        c.svg);
  text_at(&c, 40, 38, title, false, 2, 0x172b4d);
  bool percentiles = panels[0].count && panels[0].series[0].label &&
                     !strcmp(panels[0].series[0].label, "p50");
  text_at(&c, 40, 66,
          percentiles ? "p50/p95/p99 use nearest ranks, not confidence "
                        "intervals. All axes start at zero."
                      : "Median and observed min/max. Separate scales start at "
                        "zero; unavailable values are omitted.",
          false, 2, 0x43536a);
  bool ok = true;
  for (size_t p = 0; ok && p < n; p++) {
    const nb_plot_panel *panel = &panels[p];
    int top = 145 + (int)p * 400, bottom = top + 230, left = 135, right = 1370;
    double max = 0;
    size_t count = 0;
    if (!panel->count || panel->count > 3) {
      ok = false;
      break;
    }
    for (size_t s = 0; s < panel->count; s++) {
      const nb_plot_series *v = &panel->series[s];
      if (!v->count || v->count > 10000 || !v->median) {
        ok = false;
        break;
      }
      if (v->count > count)
        count = v->count;
      for (size_t i = 0; i < v->count; i++) {
        double val = v->high ? v->high[i] : v->median[i];
        if (isfinite(val) && val > max)
          max = val;
      }
    }
    if (!ok)
      break;
    max = max > 0 ? max * 1.15 : 1;
    text_at(&c, 40, top - 38, panel->title, false, 2, 0x172b4d);
    text_at(&c, left, top - 16, panel->unit, false, 1, 0x43536a);
    for (int tick = 0; tick <= 4; tick++) {
      double val = max * tick / 4;
      int y = bottom - (bottom - top) * tick / 4;
      line(&c, left, y, right, y, 0xe1e6ed);
      char buf[40];
      snprintf(buf, sizeof(buf), "%.5g", val);
      text_at(&c, 20, y + 5, buf, false, 2, 0x43536a);
    }
    line(&c, left, top, left, bottom, 0x43536a);
    line(&c, left, bottom, right, bottom, 0x43536a);
    for (size_t s = 0; s < panel->count; s++) {
      const nb_plot_series *v = &panel->series[s];
      unsigned color = colors[s];
      int lastx = 0, lasty = 0;
      bool prev = false;
      size_t available = 0;
      for (size_t i = 0; i < v->count; i++) {
        int x = count == 1 ? (left + right) / 2
                           : left + (int)((right - left) * i / (count - 1));
        double val = v->median[i];
        if (!isfinite(val)) {
          prev = false;
          continue;
        }
        available++;
        if (val < 0 || val > max) {
          ok = false;
          break;
        }
        int y = bottom - (int)((bottom - top) * val / max);
        if (prev)
          line(&c, lastx, lasty, x, y, color);
        if (v->low && v->high && isfinite(v->low[i]) && isfinite(v->high[i])) {
          int yl = bottom - (int)((bottom - top) * v->low[i] / max),
              yh = bottom - (int)((bottom - top) * v->high[i] / max);
          line(&c, x, yl, x, yh, color);
          line(&c, x - 5, yl, x + 5, yl, color);
          line(&c, x - 5, yh, x + 5, yh, color);
        }
        dot(&c, x, y, color);
        lastx = x;
        lasty = y;
        prev = true;
      }
      if (!available) {
        char note[100];
        snprintf(note, sizeof(note), "%.40s: unavailable (see summary.json)",
                 v->label ? v->label : "Series");
        text_at(&c, left + 25, top + 35 + (int)s * 26, note, false, 2, color);
      }
      int lx = left + (int)s * 400;
      line(&c, lx, bottom + 74, lx + 24, bottom + 74, color);
      text_at(&c, lx + 32, bottom + 80, v->label ? v->label : "Series", false,
              2, color);
    }
    if (panel->x_label)
      text_at(&c, (left + right) / 2, bottom + 49, panel->x_label, true, 2,
              0x43536a);
    size_t stride = (count + 6) / 7;
    const nb_plot_series *ticks = &panel->series[0];
    for (size_t i = 0; i < count; i++) {
      if (i % stride && i + 1 != count)
        continue;
      int x = count == 1 ? (left + right) / 2
                         : left + (int)((right - left) * i / (count - 1));
      char label[48];
      if (i < ticks->count && ticks->ticks && ticks->ticks[i])
        snprintf(label, sizeof(label), "%.30s", ticks->ticks[i]);
      else
        snprintf(label, sizeof(label), "%zu", i);
      text_at(&c, x, bottom + 25, label, true, 1, 0x43536a);
    }
  }
  fputs("</svg>\n", c.svg);
  if (ferror(c.svg))
    ok = false;
  if (fclose(c.svg))
    ok = false;
  if (ok) {
    snprintf(path, sizeof(path), "%s/benchmark.png", dir);
    ok = png_file(path, &c, e);
  }
  free(c.pixels);
  return ok ? true
            : nb_fail(e, e->message[0]
                             ? e->message
                             : "Invalid graph data or output failure");
}
