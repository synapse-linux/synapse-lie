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
      const disclosure = section.querySelector(".option-disclosure");
      let visible = 0;
      for (const row of section.querySelectorAll("tbody tr")) {
        row.hidden = Boolean(query) && !titleMatches && !row.textContent.toLocaleLowerCase("en-US").includes(query);
        if (!row.hidden) { visible++; count++; }
      }
      section.hidden = visible === 0;
      if (query && visible > 0 && !disclosure.open) {
        disclosure.open = true;
        disclosure.dataset.searchOpened = "true";
      } else if (!query && disclosure.dataset.searchOpened === "true") {
        disclosure.open = false;
        delete disclosure.dataset.searchOpened;
      }
    }
    status.textContent = query ? `${count} matching settings in ${sections.filter(section => !section.hidden).length} topics.` : `Browse ${sections.length} topics or search ${rows.length} settings.`;
  };
  optionSearch.addEventListener("input", filter);
  for (const link of document.querySelectorAll(".manual-sidebar nav a")) {
    link.addEventListener("click", () => { optionSearch.value = ""; filter(); });
  }
  filter();
}
