[out:json][timeout:180];
(
  nwr["amenity"~"^(townhall|fire_station|community_centre|bank|pharmacy|place_of_worship|school)$"](49.6550,6.6534,50.1495,7.2916);
  nwr["leisure"="sports_hall"](49.6550,6.6534,50.1495,7.2916);
  nwr["shop"="supermarket"](49.6550,6.6534,50.1495,7.2916);
  node["highway"="bus_stop"](49.6550,6.6534,50.1495,7.2916);
);
out center tags;
