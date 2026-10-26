// SPDX-License-Identifier: MIT
"use strict";

// Keep the page outline visible on desktop and use one disclosure on mobile.
const wideDocumentation = window.matchMedia("(min-width: 961px)");
function arrangeContents() {
  document.querySelectorAll(".page-contents").forEach(outline => {
    outline.open = wideDocumentation.matches;
  });
}
arrangeContents();
wideDocumentation.addEventListener("change", arrangeContents);

document.querySelectorAll(".page-contents a").forEach(link => {
  link.addEventListener("click", () => {
    if (!wideDocumentation.matches) link.closest("details").open = false;
  });
});
