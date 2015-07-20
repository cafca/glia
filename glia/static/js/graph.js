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
    .linkDistance(10)
    .size([radius*2, radius*2]);

//Append a SVG to the body of the html page. Assign this SVG as an object to svg
var svg = d3.select(".rk-graph").append("svg")
    .attr("width", radius*2)
    .attr("height", radius*2);

var background = svg
    .append("circle")
    .attr("cx", radius)
    .attr("cy", radius)
    .attr("r", radius)
    .style("fill", "#082a3d")

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
    .attr("class", "node")
    .attr("r", function(d) {
        return d.radius;
    })
    .style("fill", function (d) {
        return color(d.group);
    })
    .call(force.drag);

node
    .append("text")
    .attr("dx", 10)
    .attr("dy", ".35em")
    .text(function(d) { return d.name })
    .style("stroke", "white");


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


    d3.selectAll("text").attr("x", function (d) {
        return d.x;
    })
        .attr("y", function (d) {
        return d.y;
    });
});
