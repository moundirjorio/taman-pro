// Petites améliorations progressives : tout fonctionne aussi sans JavaScript.
(function () {
  "use strict";

  // Tri : soumission automatique au changement
  document.querySelectorAll("[data-autosubmit]").forEach(function (el) {
    el.addEventListener("change", function () { el.form.submit(); });
  });

  // Confirmation avant suppression
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  // Galerie photo de la page annonce
  document.querySelectorAll("[data-gallery]").forEach(function (gallery) {
    var main = gallery.querySelector("[data-gallery-main]");
    gallery.querySelectorAll(".thumb").forEach(function (thumb) {
      thumb.addEventListener("click", function () {
        if (main) main.src = thumb.dataset.src;
        gallery.querySelectorAll(".thumb").forEach(function (t) { t.classList.remove("active"); });
        thumb.classList.add("active");
      });
    });
  });

  // Afficher le numéro du vendeur
  document.querySelectorAll("[data-reveal-phone]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var phone = btn.dataset.revealPhone;
      var link = document.createElement("a");
      link.href = "tel:" + phone;
      link.className = btn.className;
      link.textContent = "📞 " + phone.replace(/(\d{2})(?=\d)/g, "$1 ");
      btn.replaceWith(link);
    });
  });

  // Formulaire d'annonce : suggestions de modèles selon la marque
  var brand = document.getElementById("brand");
  var datalist = document.getElementById("model-options");
  if (brand && datalist && window.TAMAN_MODELS) {
    var fillModels = function () {
      datalist.innerHTML = "";
      (window.TAMAN_MODELS[brand.value] || []).forEach(function (m) {
        var opt = document.createElement("option");
        opt.value = m;
        datalist.appendChild(opt);
      });
    };
    brand.addEventListener("change", fillModels);
    fillModels();
  }

  // Formulaire d'annonce : estimation du prix par l'IA
  var estimator = document.querySelector("[data-estimator]");
  if (estimator) {
    var form = estimator.closest("form");
    var estimateBtn = estimator.querySelector("[data-estimate-btn]");
    var result = estimator.querySelector("[data-estimate-result]");
    var REQUIRED = { brand: "marque", model: "modèle", year: "année", mileage_km: "kilométrage", fuel: "carburant", gearbox: "boîte de vitesses" };
    var fmt = function (n) { return n.toLocaleString("fr-FR").replace(/[\u202f\u00a0]/g, " ") + " MAD"; };
    var el = function (tag, cls, text) {
      var node = document.createElement(tag);
      if (cls) node.className = cls;
      if (text) node.textContent = text;
      return node;
    };
    var show = function (nodes, isError) {
      result.innerHTML = "";
      result.classList.toggle("is-error", !!isError);
      nodes.forEach(function (n) { result.appendChild(n); });
      result.hidden = false;
    };

    estimateBtn.addEventListener("click", function () {
      var get = function (name) { var f = form.elements[name]; return f ? f.value.trim() : ""; };
      var missing = Object.keys(REQUIRED).filter(function (k) { return !get(k); });
      if (missing.length) {
        show([el("p", null, "Pour estimer, renseignez d'abord : " + missing.map(function (k) { return REQUIRED[k]; }).join(", ") + ".")], true);
        return;
      }
      var toInt = function (name) { var v = get(name).replace(/\s/g, ""); return v ? parseInt(v, 10) : null; };
      var orNull = function (name) { return get(name) || null; };
      var payload = {
        brand: get("brand"), model: get("model"), year: toInt("year"), mileage_km: toInt("mileage_km"),
        fuel: get("fuel"), gearbox: get("gearbox"), fiscal_power: toInt("fiscal_power"), horsepower: toInt("horsepower"),
        condition: orNull("condition"), body_type: orNull("body_type"), color: orNull("color"),
        city: orNull("city"), first_hand: form.elements.first_hand ? form.elements.first_hand.checked : null
      };

      estimateBtn.disabled = true;
      estimateBtn.textContent = "Estimation…";
      fetch("/api/estimate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })
        .then(function (r) {
          return r.json().then(function (body) {
            if (!r.ok) {
              var err = new Error(typeof body.detail === "string" ? body.detail : "Vérifiez les caractéristiques saisies.");
              err.userFacing = true;
              throw err;
            }
            return body;
          });
        })
        .then(function (est) {
          var nodes = [
            el("p", "estimate-label", "Prix estimé"),
            el("p", "estimate-price", fmt(est.price_mad)),
            el("p", "estimate-range", "Fourchette probable : " + fmt(est.low_mad) + " – " + fmt(est.high_mad))
          ];
          var basis = est.comparables
            ? "Fiabilité " + est.confidence + " · basée sur " + est.comparables.toLocaleString("fr-FR") + " annonces de ce modèle."
            : "Fiabilité faible : modèle peu présent dans nos données, estimation basée sur la marque et les caractéristiques.";
          nodes.push(el("p", "hint", basis));
          if (est.ignored.length) {
            nodes.push(el("p", "hint", "Non pris en compte pour l'instant : " + est.ignored.join(", ") + "."));
          }

          var price = toInt("price_mad");
          if (price) {
            var diff = Math.round((price - est.price_mad) / est.price_mad * 100);
            var verdict = price > est.high_mad ? "au-dessus du marché" : price < est.low_mad ? "en dessous du marché" : "dans la fourchette du marché";
            nodes.push(el("p", "estimate-compare", "Votre prix (" + fmt(price) + ") est " + verdict +
              (diff ? " (" + (diff > 0 ? "+" : "") + diff + " %)." : ".")));
          }

          var apply = el("button", "btn btn-gold btn-sm", "Utiliser ce prix");
          apply.type = "button";
          apply.addEventListener("click", function () {
            form.elements.price_mad.value = est.price_mad;
            form.elements.price_mad.focus();
          });
          nodes.push(apply);
          show(nodes);
        })
        .catch(function (err) {
          show([el("p", null, err.userFacing ? err.message : "Estimation indisponible pour le moment.")], true);
        })
        .finally(function () {
          estimateBtn.disabled = false;
          estimateBtn.textContent = "Estimer le prix";
        });
    });
  }

  // Formulaire d'annonce : aperçu et limite du nombre de photos
  var photoInput = document.querySelector("[data-photo-input]");
  if (photoInput) {
    var preview = document.querySelector("[data-photo-preview]");
    var max = parseInt(photoInput.dataset.max, 10);
    var existing = parseInt(photoInput.dataset.existing, 10) || 0;

    photoInput.addEventListener("change", function () {
      preview.innerHTML = "";
      var deleted = document.querySelectorAll("input[name=delete_photos]:checked").length;
      var allowed = max - existing + deleted;
      if (photoInput.files.length > allowed) {
        alert("Vous pouvez ajouter " + allowed + " photo(s) au maximum.");
        photoInput.value = "";
        return;
      }
      Array.prototype.forEach.call(photoInput.files, function (file) {
        var img = document.createElement("img");
        img.src = URL.createObjectURL(file);
        img.alt = file.name;
        preview.appendChild(img);
      });
    });
  }
})();
