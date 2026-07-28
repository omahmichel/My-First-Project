import {
  ArrowRight,
  BarChart3,
  Boxes,
  Check,
  FileText,
  Layers3,
  Laptop,
  Menu,
  PackageSearch,
  Palette,
  ReceiptText,
  Ruler,
  ShieldCheck,
  Shirt,
  Smartphone,
  Store,
  Tablet,
  Users,
  Warehouse,
  X,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import "../../styles/landing-polish.css";

const features = [
  {
    icon: Boxes,
    title: "Inventory that matches your shop",
    description: "Track boxes, bags, pieces, colours, sizes, design codes and product variants.",
  },
  {
    icon: ReceiptText,
    title: "Professional sales documents",
    description: "Create quotations, invoices, receipts and customer payment acknowledgements.",
  },
  {
    icon: Users,
    title: "Customer credit control",
    description: "Know who owes you, when payment is due and every repayment already received.",
  },
  {
    icon: BarChart3,
    title: "Clear business reports",
    description: "View daily sales, estimated profit, stock value and products that need attention.",
  },
  {
    icon: ShieldCheck,
    title: "Staff accountability",
    description: "Track who recorded sales, changed prices, adjusted stock or applied discounts.",
  },
  {
    icon: Smartphone,
    title: "Built for everyday devices",
    description: "Use the platform comfortably on an Android phone, tablet or desktop computer.",
  },
];

export default function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="marketing-page marketing-page-polished">
      <header className="marketing-header">
        <div className="marketing-container marketing-nav">
          <Link to="/" className="marketing-brand">
            <span>S</span>
            Stock<strong>Flow</strong>
          </Link>

          <nav className={`marketing-links ${menuOpen ? "marketing-links-open" : ""}`}>
            <a href="#solutions" onClick={() => setMenuOpen(false)}>Solutions</a>
            <a href="#features" onClick={() => setMenuOpen(false)}>Features</a>
            <a href="#devices" onClick={() => setMenuOpen(false)}>Devices</a>
            <a href="#pricing" onClick={() => setMenuOpen(false)}>Pricing</a>
          </nav>

          <div className="marketing-actions">
            <Link to="/login" className="marketing-login-link">Log in</Link>
            <Link to="/register" className="marketing-primary-button">
              Start free <ArrowRight size={17} />
            </Link>
          </div>

          <button
            type="button"
            className="marketing-menu-button"
            onClick={() => setMenuOpen((current) => !current)}
            aria-label="Toggle navigation"
          >
            {menuOpen ? <X size={23} /> : <Menu size={23} />}
          </button>
        </div>
      </header>

      <main>
        <section className="marketing-hero marketing-hero-polished">
          <div className="marketing-hero-glow marketing-hero-glow-left" />
          <div className="marketing-hero-glow marketing-hero-glow-right" />

          <div className="marketing-container marketing-hero-grid marketing-hero-grid-polished">
            <div className="marketing-hero-copy">
              <div className="marketing-eyebrow">
                <span /> Inventory and invoicing for Ghanaian shops
              </div>

              <h1>
                Know your stock.
                <strong>Control every sale.</strong>
              </h1>

              <p>
                StockFlow helps building materials shops and boutiques manage products,
                issue invoices, track customer debt and understand daily performance from one place.
              </p>

              <div className="marketing-hero-actions">
                <Link to="/register" className="marketing-primary-button marketing-large-button">
                  Create free account <ArrowRight size={19} />
                </Link>
                <Link to="/login" className="marketing-secondary-button marketing-large-button">
                  Open demo dashboard
                </Link>
              </div>

              <div className="marketing-trust-row">
                <span><Check size={16} /> No complicated accounting</span>
                <span><Check size={16} /> Ghana cedi ready</span>
                <span><Check size={16} /> Mobile friendly</span>
              </div>
            </div>

            {/* Combines a real business photograph with a product dashboard preview. */}
            <div className="marketing-hero-showcase">
              <figure className="marketing-hero-photo-card">
                <img
                  src="/images/landing/hero-tablet.webp"
                  alt="Business owner using a tablet to manage her work"
                />
                <figcaption>
                  <span><Tablet size={17} /> Run the shop from anywhere</span>
                  <strong>Phone, tablet or laptop</strong>
                </figcaption>
              </figure>

              <div className="marketing-dashboard-preview marketing-dashboard-preview-floating">
                <div className="preview-topbar">
                  <span className="preview-dots"><i /><i /><i /></span>
                  <strong>Triumph Building Supplies</strong>
                  <span className="preview-avatar">MT</span>
                </div>

                <div className="preview-content">
                  <div className="preview-heading">
                    <div>
                      <span>Dashboard</span>
                      <h2>Good morning, Michael Triumph</h2>
                    </div>
                    <button type="button">New sale</button>
                  </div>

                  <div className="preview-stat-grid">
                    <article>
                      <span>Today&apos;s sales</span>
                      <strong>GH₵8,420</strong>
                      <small>32 transactions</small>
                    </article>
                    <article>
                      <span>Estimated profit</span>
                      <strong>GH₵2,180</strong>
                      <small className="preview-positive">+14.5% today</small>
                    </article>
                    <article>
                      <span>Customer debt</span>
                      <strong>GH₵3,450</strong>
                      <small>8 customers</small>
                    </article>
                  </div>

                  <div className="preview-lower-grid">
                    <div className="preview-products">
                      <div className="preview-panel-heading">
                        <div><span>Inventory overview</span><strong>Popular tile designs</strong></div>
                        <PackageSearch size={18} />
                      </div>
                      {[
                        ["tile-one", "Design 6052", "60 × 60 cm", "45 boxes"],
                        ["tile-two", "Design 2045-GR", "40 × 40 cm", "18 boxes"],
                        ["tile-three", "Design A32", "30 × 60 cm", "4 boxes"],
                      ].map(([tileClass, code, size, stock]) => (
                        <div className="preview-product-row" key={code}>
                          <span className={`preview-tile ${tileClass}`} />
                          <div><strong>{code}</strong><small>{size}</small></div>
                          <b>{stock}</b>
                        </div>
                      ))}
                    </div>

                    <div className="preview-invoice">
                      <FileText size={24} />
                      <span>Invoice generated</span>
                      <strong>INV-00284</strong>
                      <div><span>Tile Design 6052</span><b>GH₵2,220</b></div>
                      <div><span>Tile adhesive</span><b>GH₵360</b></div>
                      <footer><span>Total</span><strong>GH₵2,580</strong></footer>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="marketing-purpose-strip">
          <div className="marketing-container">
            <span>Purpose-built for</span>
            <strong><Layers3 size={19} /> Building materials shops</strong>
            <i />
            <strong><Shirt size={19} /> Boutiques and fashion stores</strong>
          </div>
        </section>

        <section className="marketing-section marketing-solutions-polished" id="solutions">
          <div className="marketing-container">
            <div className="marketing-section-heading marketing-centered-heading">
              <span>Industry-focused solutions</span>
              <h2>Built around how your shop actually operates.</h2>
              <p>
                One reliable core system with specialist inventory tools for materials and fashion businesses.
              </p>
            </div>

            <div className="marketing-solution-grid marketing-photo-solution-grid">
              <article className="marketing-solution-card marketing-photo-solution-card">
                <figure className="marketing-solution-photo">
                  <img
                    src="/images/landing/building-showroom.webp"
                    alt="Organised building materials and hardware showroom"
                  />
                  <span><Warehouse size={18} /> Building materials</span>
                </figure>
                <div className="marketing-solution-content">
                  <div className="marketing-solution-icon"><Layers3 size={28} /></div>
                  <span>Building materials</span>
                  <h3>Manage products sold by box, bag, piece, length or bundle.</h3>
                  <p>Control tiles, cement, paint, roofing sheets, plumbing items and electrical supplies.</p>
                  <ul>
                    <li><Check size={17} /> Tile design numbers and images</li>
                    <li><Check size={17} /> Box and loose-piece stock</li>
                    <li><Check size={17} /> Quotations and delivery notes</li>
                    <li><Check size={17} /> Bulk and retail pricing</li>
                  </ul>
                </div>
              </article>

              <article className="marketing-solution-card marketing-photo-solution-card">
                <figure className="marketing-solution-photo">
                  <img
                    src="/images/landing/boutique-smartphone.webp"
                    alt="Customers using a smartphone inside a modern boutique"
                  />
                  <span><Store size={18} /> Boutique retail</span>
                </figure>
                <div className="marketing-solution-content">
                  <div className="marketing-solution-icon"><Palette size={28} /></div>
                  <span>Boutiques</span>
                  <h3>Manage clothing, shoes and accessories by style and variant.</h3>
                  <p>Know exactly which sizes, colours and designs remain available at any time.</p>
                  <ul>
                    <li><Check size={17} /> Size and colour variants</li>
                    <li><Check size={17} /> Product images and style codes</li>
                    <li><Check size={17} /> Returns and exchanges</li>
                    <li><Check size={17} /> Customer purchase history</li>
                  </ul>
                </div>
              </article>
            </div>
          </div>
        </section>

        <section className="marketing-section marketing-tile-section">
          <div className="marketing-container marketing-tile-grid">
            <div className="marketing-tile-catalogue">
              <div className="marketing-catalogue-heading">
                <div><span>Tile catalogue</span><strong>Select by design number</strong></div>
                <label><PackageSearch size={17} /><input value="6052" readOnly /></label>
              </div>
              <div className="marketing-design-grid">
                {["6052", "A32", "2045-GR"].map((code, index) => (
                  <article className={index === 0 ? "marketing-design-selected" : ""} key={code}>
                    <div className={`marketing-large-tile tile-${index + 1}`} />
                    <strong>Design {code}</strong>
                    <span>{index === 0 ? "60 × 60 cm" : index === 1 ? "30 × 60 cm" : "40 × 40 cm"}</span>
                  </article>
                ))}
              </div>
              <div className="marketing-tile-details">
                <div><span>Available stock</span><strong>45 boxes + 3 pieces</strong></div>
                <div><span>Coverage</span><strong>1.44 m² per box</strong></div>
                <div><span>Selling price</span><strong>GH₵185 per box</strong></div>
              </div>
            </div>

            <div className="marketing-tile-copy">
              <span>Advanced tile inventory</span>
              <h2>Help customers find the exact tile design they want.</h2>
              <p>
                Organise tiles by design number, image, size, finish, colour, brand and batch.
                Staff can search a code and instantly see price and availability.
              </p>
              <ul>
                <li><Ruler size={21} /><div><strong>Coverage calculations</strong><span>Record pieces and square metres per box.</span></div></li>
                <li><Boxes size={21} /><div><strong>Boxes and loose pieces</strong><span>Keep both quantities accurate.</span></div></li>
                <li><PackageSearch size={21} /><div><strong>Batch tracking</strong><span>Avoid mixing slightly different production batches.</span></div></li>
              </ul>
            </div>
          </div>
        </section>

        {/* Shows business owners that the application works across common devices. */}
        <section className="marketing-section marketing-device-section" id="devices">
          <div className="marketing-container marketing-device-grid">
            <figure className="marketing-device-photo">
              <img
                src="/images/landing/business-laptop.webp"
                alt="Business owner using a smartphone and laptop"
              />
              <div className="marketing-device-photo-badge">
                <Check size={17} /> Your records stay connected
              </div>
            </figure>

            <div className="marketing-device-copy">
              <span>Work from anywhere</span>
              <h2>Check your shop even when you are not behind the counter.</h2>
              <p>
                Record sales on a phone, review stock on a tablet and analyse reports on a laptop.
                The same business information remains available across your everyday devices.
              </p>

              <div className="marketing-device-list">
                <article>
                  <Smartphone size={22} />
                  <div><strong>Phone</strong><span>Fast sales and stock checks</span></div>
                </article>
                <article>
                  <Tablet size={22} />
                  <div><strong>Tablet</strong><span>Comfortable counter operation</span></div>
                </article>
                <article>
                  <Laptop size={22} />
                  <div><strong>Laptop</strong><span>Reports and administration</span></div>
                </article>
              </div>

              <Link to="/register" className="marketing-primary-button marketing-large-button">
                Start managing your shop <ArrowRight size={18} />
              </Link>
            </div>
          </div>
        </section>

        <section className="marketing-section" id="features">
          <div className="marketing-container">
            <div className="marketing-section-heading">
              <span>Everything in one place</span>
              <h2>Run a more organised and accountable shop.</h2>
            </div>
            <div className="marketing-feature-grid">
              {features.map(({ icon: Icon, title, description }) => (
                <article key={title}>
                  <div><Icon size={23} /></div>
                  <h3>{title}</h3>
                  <p>{description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="marketing-section marketing-pricing-section" id="pricing">
          <div className="marketing-container">
            <div className="marketing-section-heading marketing-centered-heading">
              <span>Simple starting plans</span>
              <h2>Begin small and upgrade as the business grows.</h2>
            </div>
            <div className="marketing-pricing-grid">
              {[
                ["Starter", "30", "For owner-managed shops", ["Inventory management", "Invoices and receipts", "Customer debt"]],
                ["Business", "70", "For active shops with staff", ["Everything in Starter", "Staff accounts", "Advanced reports"]],
                ["Pro", "150", "For growing businesses", ["Everything in Business", "Priority support", "More business controls"]],
              ].map(([name, price, description, items], index) => (
                <article className={index === 1 ? "marketing-price-featured" : ""} key={name}>
                  {index === 1 ? <b className="marketing-popular-label">Most popular</b> : null}
                  <span>{name}</span>
                  <h3>GH₵{price}<small>/month</small></h3>
                  <p>{description}</p>
                  <ul>{items.map((item) => <li key={item}><Check size={17} />{item}</li>)}</ul>
                  <Link to="/register" className={index === 1 ? "marketing-primary-button" : "marketing-secondary-button"}>
                    Start free trial
                  </Link>
                </article>
              ))}
            </div>
            <p className="marketing-pricing-note">Pricing remains a proposal until pilot testing is completed.</p>
          </div>
        </section>

        <section className="marketing-cta-section">
          <div className="marketing-container marketing-cta-card marketing-cta-card-polished">
            <div>
              <span>Ready to organise your shop?</span>
              <h2>Stop guessing what you sold, what remains and who owes you.</h2>
              <p>Open the working frontend demo and explore the complete application interface.</p>
            </div>
            <div>
              <Link to="/register" className="marketing-light-button">Create free account <ArrowRight size={18} /></Link>
              <Link to="/login" className="marketing-outline-button">Open demo</Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="marketing-footer">
        <div className="marketing-container marketing-footer-grid">
          <div>
            <Link to="/" className="marketing-brand"><span>S</span>Stock<strong>Flow</strong></Link>
            <p>Inventory, invoicing and business control for Ghanaian building materials shops and boutiques.</p>
          </div>
          <div><strong>Product</strong><a href="#features">Features</a><a href="#solutions">Solutions</a><a href="#pricing">Pricing</a></div>
          <div><strong>Account</strong><Link to="/login">Log in</Link><Link to="/register">Create account</Link></div>
        </div>
        <div className="marketing-container marketing-footer-bottom">
          <span>© 2026 StockFlow. All rights reserved.</span><span>Built for Ghanaian businesses.</span>
        </div>
      </footer>
    </div>
  );
}