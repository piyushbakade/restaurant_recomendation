/**
 * GourmetAI - Interactive Frontend Reactivity & API Integration
 * Supports Top Picks view, All Recommendations view, and Max 6 per Page Pagination.
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements - Inputs
  const form = document.getElementById("recommendation-form");
  const submitBtn = document.getElementById("submit-btn");
  const locationInput = document.getElementById("location-input");
  const locationChips = document.querySelectorAll("#location-chips .chip");
  const cuisineButtons = document.querySelectorAll("#cuisine-grid .cuisine-btn");
  const budgetSlider = document.getElementById("budget-slider");
  const budgetValue = document.getElementById("budget-value");
  const ratingPills = document.querySelectorAll("#rating-pills .rating-pill");
  const vibeInput = document.getElementById("vibe-input");
  const vibeChips = document.querySelectorAll(".vibe-chip");
  const onlineOrderCheck = document.getElementById("online-order-check");
  const bookTableCheck = document.getElementById("book-table-check");

  // DOM Elements - Outputs & States
  const initialState = document.getElementById("initial-state");
  const resultsMetaBanner = document.getElementById("results-meta-banner");
  const metaLocationTitle = document.getElementById("meta-location-title");
  const metaDetails = document.getElementById("meta-details");
  const statLatency = document.getElementById("stat-latency");
  const statProvider = document.getElementById("stat-provider");
  const relaxationBanner = document.getElementById("relaxation-banner");
  const relaxationNotesList = document.getElementById("relaxation-notes-list");
  const loadingState = document.getElementById("loading-state");
  const loadingStatusText = document.getElementById("loading-status-text");
  const recommendationsContainer = document.getElementById("recommendations-container");
  const emptyState = document.getElementById("empty-state");
  const resetFiltersBtn = document.getElementById("reset-filters-btn");

  // DOM Elements - View Controls & Pagination
  const viewControlsBar = document.getElementById("view-controls-bar");
  const tabTopPicks = document.getElementById("tab-top-picks");
  const tabAllOptions = document.getElementById("tab-all-options");
  const badgeTopCount = document.getElementById("badge-top-count");
  const badgeTotalCount = document.getElementById("badge-total-count");
  const pageItemRange = document.getElementById("page-item-range");
  const pageTotalItems = document.getElementById("page-total-items");
  const paginationContainer = document.getElementById("pagination-container");
  const prevPageBtn = document.getElementById("prev-page-btn");
  const nextPageBtn = document.getElementById("next-page-btn");
  const paginationNumbers = document.getElementById("pagination-numbers");

  // Application State
  let activeRating = null;
  let allRecommendations = [];
  let currentViewMode = "top"; // "top" (first view) or "all" (paginated view)
  let currentPage = 1;
  const PAGE_SIZE = 6; // Strictly maximum 6 options per page

  // 1. Location Chips Toggle
  locationChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      if (chip.classList.contains("active")) {
        chip.classList.remove("active");
        locationInput.value = "";
      } else {
        locationChips.forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        locationInput.value = chip.dataset.location;
      }
    });
  });

  locationInput.addEventListener("input", () => {
    const val = locationInput.value.toLowerCase().trim();
    locationChips.forEach((chip) => {
      if (val && chip.dataset.location.toLowerCase() === val) {
        chip.classList.add("active");
      } else {
        chip.classList.remove("active");
      }
    });
  });

  // 2. Cuisine Grid Multi-select Toggle
  cuisineButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      btn.classList.toggle("active");
    });
  });

  // 3. Budget Slider Live Display
  budgetSlider.addEventListener("input", (e) => {
    const val = parseInt(e.target.value, 10);
    budgetValue.textContent = val.toLocaleString("en-IN");
  });

  // 4. Rating Pills Toggle
  ratingPills.forEach((pill) => {
    pill.addEventListener("click", () => {
      if (pill.classList.contains("active")) {
        pill.classList.remove("active");
        activeRating = null;
      } else {
        ratingPills.forEach((p) => p.classList.remove("active"));
        pill.classList.add("active");
        activeRating = parseFloat(pill.dataset.rating);
      }
    });
  });

  // 5. Vibe Chips Autofill
  vibeChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      vibeInput.value = chip.dataset.vibe;
    });
  });

  // 6. Reset Filters Button
  if (resetFiltersBtn) {
    resetFiltersBtn.addEventListener("click", () => {
      locationInput.value = "";
      locationChips.forEach((c) => c.classList.remove("active"));
      budgetSlider.value = 1000;
      budgetValue.textContent = "1,000";
      cuisineButtons.forEach((b) => b.classList.remove("active"));
      ratingPills.forEach((p) => p.classList.remove("active"));
      activeRating = null;
      vibeInput.value = "";
      onlineOrderCheck.checked = false;
      bookTableCheck.checked = false;
      allRecommendations = [];
      currentPage = 1;
      currentViewMode = "top";
      recommendationsContainer.innerHTML = "";
      resultsMetaBanner.classList.add("hidden");
      if (viewControlsBar) viewControlsBar.classList.add("hidden");
      if (paginationContainer) paginationContainer.classList.add("hidden");
      relaxationBanner.classList.add("hidden");
      emptyState.classList.add("hidden");
      if (initialState) initialState.classList.remove("hidden");
    });
  }

  // 7. View Mode Tabs Toggle (Top Picks vs All Recommendations)
  if (tabTopPicks) {
    tabTopPicks.addEventListener("click", () => {
      if (currentViewMode !== "top") {
        currentViewMode = "top";
        currentPage = 1;
        renderCurrentView(false);
      }
    });
  }

  if (tabAllOptions) {
    tabAllOptions.addEventListener("click", () => {
      if (currentViewMode !== "all") {
        currentViewMode = "all";
        currentPage = 1;
        renderCurrentView(false);
      }
    });
  }

  // 8. Pagination Previous / Next Buttons
  if (prevPageBtn) {
    prevPageBtn.addEventListener("click", () => {
      if (currentPage > 1) {
        currentPage--;
        renderCurrentView(true);
      }
    });
  }

  if (nextPageBtn) {
    nextPageBtn.addEventListener("click", () => {
      const totalPages = Math.ceil(allRecommendations.length / PAGE_SIZE);
      if (currentPage < totalPages) {
        currentPage++;
        renderCurrentView(true);
      }
    });
  }

  // 9. Form Submit Handler
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    executeSearch();
  });

  // Multi-step Loading Animation Helper
  function runLoadingSequence() {
    if (initialState) initialState.classList.add("hidden");
    loadingState.classList.remove("hidden");
    recommendationsContainer.innerHTML = "";
    resultsMetaBanner.classList.add("hidden");
    if (viewControlsBar) viewControlsBar.classList.add("hidden");
    if (paginationContainer) paginationContainer.classList.add("hidden");
    relaxationBanner.classList.add("hidden");
    emptyState.classList.add("hidden");
    submitBtn.classList.add("loading");

    const steps = [
      "Scanning 12,000+ verified Bangalore restaurants...",
      "Applying budget & multi-factor heuristic ranking...",
      "AI Concierge curating top matches & all options...",
    ];

    let stepIdx = 0;
    loadingStatusText.textContent = steps[0];

    const timer = setInterval(() => {
      stepIdx++;
      if (stepIdx < steps.length) {
        loadingStatusText.textContent = steps[stepIdx];
      } else {
        clearInterval(timer);
      }
    }, 280);

    return timer;
  }

  async function executeSearch() {
    const location = locationInput.value.trim();
    if (!location) {
      alert("Please enter a location or select a popular neighborhood.");
      locationInput.focus();
      return;
    }

    const selectedCuisines = Array.from(
      document.querySelectorAll("#cuisine-grid .cuisine-btn.active")
    ).map((b) => b.dataset.cuisine);

    const payload = {
      location: location,
      cuisines: selectedCuisines,
      max_budget: parseInt(budgetSlider.value, 10),
      min_rating: activeRating !== null ? activeRating : undefined,
      vibe_or_notes: vibeInput.value.trim() || undefined,
      online_order_only: onlineOrderCheck.checked,
      book_table_only: bookTableCheck.checked,
      top_k: 30, // Request up to 30 ranked matches so user can browse all options
    };

    const loadingTimer = runLoadingSequence();

    try {
      const response = await fetch("/api/recommendations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      clearInterval(loadingTimer);
      submitBtn.classList.remove("loading");
      loadingState.classList.add("hidden");

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error (${response.status})`);
      }

      const data = await response.json();
      renderResults(data);
    } catch (err) {
      clearInterval(loadingTimer);
      submitBtn.classList.remove("loading");
      loadingState.classList.add("hidden");
      alert(`Recommendation request failed: ${err.message}`);
    }
  }

  function renderResults(data) {
    const { recommendations, query_summary, total_candidates_found, was_relaxed, relaxation_notes, meta, provider_used } = data;

    allRecommendations = recommendations || [];
    currentViewMode = "top";
    currentPage = 1;

    // 1. Meta Banner
    resultsMetaBanner.classList.remove("hidden");
    metaLocationTitle.textContent = `${query_summary.location || "Bangalore"} (${query_summary.cluster || "Metro"})`;
    metaDetails.textContent = `Showing curated recommendations from ${total_candidates_found} candidates found`;
    statLatency.textContent = `⚡ ${meta?.execution_time_ms || 45} ms`;
    statProvider.textContent = `🤖 ${provider_used === "GeminiProvider" ? "Gemini 3.5 Flash" : "AI Concierge"}`;

    // Smoothly scroll down to suggestions so user immediately sees results
    setTimeout(() => {
      resultsMetaBanner.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 100);

    // 2. Relaxation Banner
    if (was_relaxed && relaxation_notes && relaxation_notes.length > 0) {
      relaxationBanner.classList.remove("hidden");
      relaxationNotesList.innerHTML = relaxation_notes.map((n) => `<li>${n}</li>`).join("");
    } else {
      relaxationBanner.classList.add("hidden");
    }

    // 3. Render Current View with Cards & Pagination
    renderCurrentView(false);
  }

  function renderCurrentView(smoothScroll = false) {
    recommendationsContainer.innerHTML = "";

    if (!allRecommendations || allRecommendations.length === 0) {
      emptyState.classList.remove("hidden");
      if (viewControlsBar) viewControlsBar.classList.add("hidden");
      if (paginationContainer) paginationContainer.classList.add("hidden");
      return;
    }

    emptyState.classList.add("hidden");
    if (viewControlsBar) viewControlsBar.classList.remove("hidden");

    let listToRender = [];
    let startIdx = 0;
    let endIdx = 0;
    let totalPages = 1;

    const topCount = Math.min(5, allRecommendations.length);
    if (badgeTopCount) badgeTopCount.textContent = `Top ${topCount}`;
    if (badgeTotalCount) badgeTotalCount.textContent = `${allRecommendations.length}`;

    if (currentViewMode === "top") {
      // Top 5 first view
      listToRender = allRecommendations.slice(0, 5);
      startIdx = 1;
      endIdx = listToRender.length;
      if (pageItemRange) pageItemRange.textContent = `1–${endIdx}`;
      if (pageTotalItems) pageTotalItems.textContent = `${allRecommendations.length}`;

      if (tabTopPicks) {
        tabTopPicks.classList.add("active");
        tabTopPicks.setAttribute("aria-selected", "true");
      }
      if (tabAllOptions) {
        tabAllOptions.classList.remove("active");
        tabAllOptions.setAttribute("aria-selected", "false");
      }

      // Hide bottom pagination controls when in top picks mode
      if (paginationContainer) paginationContainer.classList.add("hidden");
    } else {
      // All Recommendations View: strictly maximum 6 on each page
      totalPages = Math.ceil(allRecommendations.length / PAGE_SIZE) || 1;
      if (currentPage > totalPages) currentPage = totalPages;
      if (currentPage < 1) currentPage = 1;

      const offset = (currentPage - 1) * PAGE_SIZE;
      listToRender = allRecommendations.slice(offset, offset + PAGE_SIZE);
      startIdx = offset + 1;
      endIdx = offset + listToRender.length;

      if (pageItemRange) pageItemRange.textContent = `${startIdx}–${endIdx}`;
      if (pageTotalItems) pageTotalItems.textContent = `${allRecommendations.length}`;

      if (tabAllOptions) {
        tabAllOptions.classList.add("active");
        tabAllOptions.setAttribute("aria-selected", "true");
      }
      if (tabTopPicks) {
        tabTopPicks.classList.remove("active");
        tabTopPicks.setAttribute("aria-selected", "false");
      }

      // Render pagination numbers and previous/next controls
      renderPaginationControls(totalPages);
    }

    // Render cards for the active page
    listToRender.forEach((rec) => {
      recommendationsContainer.appendChild(createRestaurantCard(rec));
    });

    // In 'top' mode, if there are more than 5 total recommendations, append a friendly "Check all X options" CTA card
    if (currentViewMode === "top" && allRecommendations.length > 5) {
      const moreCard = document.createElement("div");
      moreCard.className = "view-all-cta-card glass-card";
      moreCard.innerHTML = `
        <div class="cta-content">
          <span class="cta-icon" aria-hidden="true">🔍</span>
          <div>
            <h4 class="cta-title">Want to explore all options?</h4>
            <p class="cta-desc">Found <strong>${allRecommendations.length} matching restaurants</strong> for your taste. Browse all options 6 at a time.</p>
          </div>
        </div>
        <button type="button" id="btn-see-all-recommendations" class="cta-browse-btn">
          Check All ${allRecommendations.length} Options &rarr;
        </button>
      `;
      recommendationsContainer.appendChild(moreCard);
      const btnSeeAll = moreCard.querySelector("#btn-see-all-recommendations");
      if (btnSeeAll) {
        btnSeeAll.addEventListener("click", () => {
          currentViewMode = "all";
          currentPage = 1;
          renderCurrentView(true);
        });
      }
    }

    // Smooth scroll to top of view when navigating pages
    if (smoothScroll && viewControlsBar) {
      viewControlsBar.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function renderPaginationControls(totalPages) {
    if (!paginationContainer) return;
    if (totalPages <= 1) {
      paginationContainer.classList.add("hidden");
      return;
    }

    paginationContainer.classList.remove("hidden");
    prevPageBtn.disabled = currentPage === 1;
    nextPageBtn.disabled = currentPage === totalPages;

    paginationNumbers.innerHTML = "";
    for (let p = 1; p <= totalPages; p++) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `page-num-btn ${p === currentPage ? "active" : ""}`;
      btn.textContent = p;
      btn.setAttribute("aria-label", `Go to page ${p}`);
      btn.addEventListener("click", () => {
        if (currentPage !== p) {
          currentPage = p;
          renderCurrentView(true);
        }
      });
      paginationNumbers.appendChild(btn);
    }
  }

  function createRestaurantCard(rec) {
    const card = document.createElement("article");
    card.className = "restaurant-card glass-card";

    const ratingFormatted = rec.rating != null ? rec.rating.toFixed(1) : "New";
    const votesFormatted = (rec.votes || 0).toLocaleString("en-IN");
    const priceFormatted = (rec.price_for_two || 0).toLocaleString("en-IN");

    // Cuisines pills
    const cuisinesHtml = (rec.cuisines || [])
      .map((c) => `<span class="cuisine-tag">${escapeHtml(c)}</span>`)
      .join("");

    // Dishes pills
    const dishesHtml = (rec.popular_dishes || [])
      .slice(0, 4)
      .map((d) => `<span class="dish-pill">${escapeHtml(d)}</span>`)
      .join("");

    // External link
    const urlHtml = rec.url
      ? `<a href="${escapeHtml(rec.url)}" target="_blank" rel="noopener noreferrer" class="action-link">View on Zomato ↗</a>`
      : "";

    card.innerHTML = `
      <div class="card-header">
        <div class="card-title-group">
          <span class="rank-badge" title="Match Rank #${rec.match_rank}">#${rec.match_rank}</span>
          <div>
            <h3 class="restaurant-name">${escapeHtml(rec.name)}</h3>
            <p class="card-locality">📍 ${escapeHtml(rec.location)} &middot; <span class="cluster-tag">${escapeHtml(rec.location_cluster)}</span></p>
          </div>
        </div>
        <div class="card-metrics">
          <span class="metric-pill metric-rating">★ ${ratingFormatted} <span class="metric-votes">(${votesFormatted})</span></span>
          <span class="metric-pill metric-cost">₹${priceFormatted} for two</span>
        </div>
      </div>

      <div class="cuisine-tags">
        ${cuisinesHtml}
      </div>

      <div class="ai-recommendation-box">
        <div class="ai-header">
          <span aria-hidden="true">✨</span>
          <span>Why This Matches Your Taste</span>
        </div>
        <p class="ai-reason-text">${escapeHtml(rec.recommendation_reason)}</p>
      </div>

      ${
        dishesHtml
          ? `<div class="signatures-row">
               <span class="signatures-label">Popular Dishes:</span>
               ${dishesHtml}
             </div>`
          : ""
      }

      <div class="card-footer">
        ${urlHtml}
      </div>
    `;

    return card;
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
