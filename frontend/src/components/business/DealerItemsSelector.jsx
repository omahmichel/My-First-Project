import { Check, PackageSearch, Plus, Search, X } from "lucide-react";
import { useMemo, useState } from "react";

import {
  businessTypeDealerLabel,
  dealerCatalogForBusinessType,
} from "../../data/dealerCatalog";

const MAX_SELECTED_ITEMS = 10;

function sameItem(left, right) {
  return String(left || "").trim().toLowerCase() ===
    String(right || "").trim().toLowerCase();
}

export default function DealerItemsSelector({
  businessType,
  value = [],
  onChange,
  compact = false,
}) {
  const [search, setSearch] = useState("");
  const [customItem, setCustomItem] = useState("");
  const [message, setMessage] = useState("");

  const selectedItems = Array.isArray(value) ? value : [];
  const baseCatalog = dealerCatalogForBusinessType(businessType);

  const availableItems = useMemo(() => {
    const customSelected = selectedItems.filter(
      (item) => !baseCatalog.some((baseItem) => sameItem(baseItem, item)),
    );
    return [...baseCatalog, ...customSelected];
  }, [baseCatalog, selectedItems]);

  const filteredItems = availableItems.filter((item) =>
    item.toLowerCase().includes(search.trim().toLowerCase()),
  );

  function isSelected(item) {
    return selectedItems.some((selected) => sameItem(selected, item));
  }

  function toggleItem(item) {
    setMessage("");

    if (isSelected(item)) {
      onChange(selectedItems.filter((selected) => !sameItem(selected, item)));
      return;
    }

    if (selectedItems.length >= MAX_SELECTED_ITEMS) {
      setMessage(`Choose up to ${MAX_SELECTED_ITEMS} items that best describe the business.`);
      return;
    }

    onChange([...selectedItems, item]);
  }

  function removeItem(item) {
    setMessage("");
    onChange(selectedItems.filter((selected) => !sameItem(selected, item)));
  }

  function addCustomItem() {
    const item = customItem.replace(/\s+/g, " ").trim();
    setMessage("");

    if (!item) {
      setMessage("Type the missing item before adding it.");
      return;
    }

    if (item.length > 60) {
      setMessage("Keep each item name within 60 characters.");
      return;
    }

    const existing = availableItems.find((candidate) => sameItem(candidate, item));

    if (existing) {
      if (!isSelected(existing)) toggleItem(existing);
      setCustomItem("");
      return;
    }

    if (selectedItems.length >= MAX_SELECTED_ITEMS) {
      setMessage(`Choose up to ${MAX_SELECTED_ITEMS} items that best describe the business.`);
      return;
    }

    onChange([...selectedItems, item]);
    setCustomItem("");
  }

  const dealerLabel = businessTypeDealerLabel(businessType);

  return (
    <section
      className={`rounded-2xl border border-emerald-100 bg-white/95 shadow-sm ${
        compact ? "mt-5 p-4" : "mt-6 p-5 md:p-6"
      }`}
      aria-label="Business dealer catalogue"
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
          <div className="max-w-2xl">
            <span className="inline-flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.12em] text-emerald-700">
              <PackageSearch size={16} />
              Dealer profile
            </span>
            <h2 className="mt-1 text-base font-extrabold text-slate-900 md:text-lg">
              What does this business deal in?
            </h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Select the {dealerLabel} you sell. These choices describe the
              dealer on invoices, receipts and waybills.
            </p>
          </div>
          <span className="inline-flex w-fit rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1.5 text-[11px] font-bold text-emerald-800">
            {selectedItems.length}/{MAX_SELECTED_ITEMS} selected
          </span>
        </div>

        {selectedItems.length ? (
          <div className="flex flex-wrap gap-2" aria-label="Selected dealer items">
            {selectedItems.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => removeItem(item)}
                className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-[11px] font-bold text-emerald-800 transition hover:bg-emerald-100"
                title={`Remove ${item}`}
              >
                {item}
                <X size={13} />
              </button>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
            No items selected yet. Choose the products that best describe the business.
          </div>
        )}

        <label className="relative block">
          <Search size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={`Search ${dealerLabel}...`}
            style={{ paddingLeft: "2.75rem" }}
            className="min-h-10 w-full rounded-xl border border-slate-200 bg-white py-2 pr-3 text-sm text-slate-800 outline-none transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
          />
        </label>

        <div className="grid max-h-64 grid-cols-1 gap-2 overflow-y-auto pr-1 sm:grid-cols-2 lg:grid-cols-3">
          {filteredItems.map((item) => {
            const selected = isSelected(item);
            return (
              <button
                key={item}
                type="button"
                aria-pressed={selected}
                onClick={() => toggleItem(item)}
                className={`flex min-h-10 items-center justify-between gap-2 rounded-xl border px-3 py-2 text-left text-xs font-semibold transition ${
                  selected
                    ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                    : "border-slate-200 bg-white text-slate-700 hover:border-emerald-200 hover:bg-emerald-50/60"
                }`}
              >
                <span>{item}</span>
                {selected ? (
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white">
                    <Check size={12} />
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>

        {!filteredItems.length ? (
          <p className="text-xs text-slate-500">
            No catalogue item matches that search. Add it below if the business deals in it.
          </p>
        ) : null}

        <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
          <div className="mb-2">
            <strong className="text-xs text-slate-800">Can't find an item?</strong>
            <p className="mt-0.5 text-[11px] leading-4 text-slate-500">
              Add a custom item. StockFlow saves it with this business and keeps
              it in the dealer profile.
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              value={customItem}
              onChange={(event) => {
                setCustomItem(event.target.value);
                setMessage("");
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  addCustomItem();
                }
              }}
              maxLength={60}
              placeholder="e.g. Marble slabs"
              className="min-h-10 flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
            />
            <button
              type="button"
              onClick={addCustomItem}
              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white transition hover:bg-emerald-800"
            >
              <Plus size={15} />
              Add item
            </button>
          </div>

          {message ? (
            <p className="mt-2 text-[11px] font-semibold text-amber-700" role="status">
              {message}
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
