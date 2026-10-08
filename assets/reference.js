// SPDX-License-Identifier: MIT
"use strict";

const optionSearch = document.getElementById("option-search");
if (optionSearch) {
  const sections = [...document.querySelectorAll(".option-section")];
  const rows = sections.flatMap(section => [...section.querySelectorAll("tbody tr")]);
  const status = document.getElementById("option-search-status");
  const filter = () => {
    const query = optionSearch.value.trim().toLocaleLowerCase("en-US");
    let count = 0;
    for (const section of sections) {
      const titleMatches = section.querySelector("h2").textContent.toLocaleLowerCase("en-US").includes(query);
      let visible = 0;
      for (const row of section.querySelectorAll("tbody tr")) {
        row.hidden = Boolean(query) && !titleMatches && !row.textContent.toLocaleLowerCase("en-US").includes(query);
        if (!row.hidden) { visible++; count++; }
      }
      section.hidden = visible === 0;
    }
    status.textContent = query ? `Showing ${count} of ${rows.length} option entries.` : `Showing all ${rows.length} option entries.`;
  };
  optionSearch.addEventListener("input", filter);
  for (const link of document.querySelectorAll(".manual-sidebar nav a")) {
    link.addEventListener("click", () => { optionSearch.value = ""; filter(); });
  }
  filter();
}
