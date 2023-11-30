import fs from "fs";
import { JSONConverter } from "@deck.gl/json";
// import { HexagonLayer } from "@deck.gl/aggregation-layers";

const configuration = {
    // layers: require('@deck.gl/layers')
};

const jsonConverter = new JSONConverter({ configuration });

const layer = jsonConverter.convert(fs.readFileSync("layers.json").toString());
console.log(layer);

// const layer2 = new HexagonLayer({
//   id: "hexagon-layer",
//   data: [],
//   pickable: true,
//   extruded: true,
//   radius: 200,
//   elevationScale: 4,
//   getPosition: (d) => d.COORDINATES,
// });

// console.log(layer2)