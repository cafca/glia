/*
    Javascript Graph
    ~~~~~

    Visualise frontpage information sources

    Adapted from an example by Mike Bostock [1]

    [1]: http://bl.ocks.org/mbostock/4062045

    :copyright: (c) 2015 by Vincent Ahrend.
*/

//Constants for the SVG
var radius = 100;

//Set up the colour scale
var color = d3.scale.ordinal()
    .domain([0, 1, 2, 3, 4, 5, 6])
    .range(['#c81d25','#ffffff','#0b3954','#f5cb5c','#8bb174','#129490','#ef3054'])

//Set up the force layout
var force = d3.layout.force()
    .charge(-120)
    .gravity(0.2)
    .linkDistance(10)
    .size([radius*2, radius*2]);

//Append a SVG to the body of the html page. Assign this SVG as an object to svg
var svg = d3.select(".rk-graph").append("svg")
    .attr("width", radius*2)
    .attr("height", radius*2);

var background = svg
    .append("circle")
    .attr("class", "background")
    .attr("cx", radius)
    .attr("cy", radius)
    .attr("r", radius)
    .style("fill", "#082a3d");

//Read the data from the graph_json element
var graph_json = document.getElementById('graph-json').innerHTML;
graph = JSON.parse(graph_json);

//Creates the graph data structure out of the json data
force.nodes(graph.nodes)
    .links(graph.links)
    .start();

//Create all the line svgs but without locations yet
var link = svg.selectAll(".link")
    .data(graph.links)
    .enter().append("line")
    .attr("class", "link");

//Do the same with the circles for the nodes - no
var node = svg.selectAll(".node")
    .data(graph.nodes)
    .enter().append("circle")
    .attr("r", function(d) {
        return d.radius;
    })
    .style("fill", function (d) {
        if (d.group == 2) {
            return "#" + d.color;
        } else {
            return color(d.group);
        }
    })
    .attr("class", "node")
    .call(force.drag);

node
    .filter(function(d) {return d["group"] == 1; })
    .style("animation-name", "shift")
    .style("animation-iteration-count", "infinite")
    .style("animation-duration", function(d) {
        return d.anim + "s";
    });

$(".node").hover(function() {
    var d = $(this).prop("__data__");
    $("#rk-graph-label").html(d["name"]);
    $(".rk-graph").parent().attr("href", d["url"]);
})

$(".rk-graph").mouseleave(function () {
    $(".rk-graph-label").html("Frontpage");
    $(".rk-graph").parent().attr("href", "/");
})

//Now we are giving the SVGs co-ordinates - the force layout is generating the co-ordinates which this code is using to update the attributes of the SVG elements
force.on("tick", function () {
    link.attr("x1", function (d) {
        return d.source.x;
    })
        .attr("y1", function (d) {
        return d.source.y;
    })
        .attr("x2", function (d) {
        return d.target.x;
    })
        .attr("y2", function (d) {
        return d.target.y;
    });

    node.attr("cx", function (d) {
        return d.x;
    })
        .attr("cy", function (d) {
        return d.y;
    });
});

force.start();
for (var i=0; i<5000; ++i) force.tick();
force.stop();
