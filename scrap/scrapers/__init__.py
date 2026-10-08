"""One module per Moroccan car-ad site; each exposes SITE (see common.Site)."""
from . import avito, kifal, moteur, wandaloo

SITES = {site.name: site for site in (avito.SITE, moteur.SITE, wandaloo.SITE, kifal.SITE)}
