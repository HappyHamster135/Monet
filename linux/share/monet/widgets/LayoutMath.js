// Logical pixels throughout. Keep edge relationships; pack only when they collide.
function overlaps(a, b, gap) {
    return a.x < b.x + b.width + gap && a.x + a.width + gap > b.x
        && a.y < b.y + b.height + gap && a.y + a.height + gap > b.y;
}

function arrange(items, before, area, cell) {
    var gap = cell, edge = cell, placed = [], wanted = [], crowded = false;
    var ratio = Math.min(1, area.width / before.width, area.height / before.height);
    var ordered = items.slice().sort(function(a, b) { return b.width*b.height - a.width*a.height || a.id-b.id; });
    ordered.forEach(function(item) {
        var w = Math.min(area.width - 2*edge, Math.ceil(Math.max(item.minWidth, item.width*ratio)/cell)*cell);
        var h = Math.min(area.height - 2*edge, Math.ceil(Math.max(item.minHeight, item.height*ratio)/cell)*cell);
        var x = edge + Math.max(0, Math.min(1, item.x / Math.max(1, before.width-item.width))) * Math.max(0, area.width-w-2*edge);
        var y = edge + Math.max(0, Math.min(1, item.y / Math.max(1, before.height-item.height))) * Math.max(0, area.height-h-2*edge);
        wanted.push({id:item.id,x:x,y:y,width:w,height:h});
        var best = null, distance = Infinity;
        for (var yy=edge; yy+h<=area.height-edge; yy+=cell) {
            for (var xx=edge; xx+w<=area.width-edge; xx+=cell) {
                var r = {id:item.id, x:xx, y:yy, width:w, height:h};
                if (placed.some(function(p) { return overlaps(p,r,gap); })) continue;
                var d = (xx-x)*(xx-x)+(yy-y)*(yy-y);
                if (d<distance) { best=r; distance=d; }
            }
        }
        // A crowded desktop may not fit every minimum-sized widget; keep it reachable.
        if (!best) crowded = true;
        placed.push(best || {id:item.id, x:Math.max(edge,Math.min(x,area.width-w-edge)),
                            y:Math.max(edge,Math.min(y,area.height-h-edge)),width:w,height:h});
    });
    // The closest greedy placement can block a later widget even when all fit.
    // Try neighbouring edges before allowing overlap, with bounded work for
    // desktops containing many third-party widgets.
    if (crowded) {
        var budget=20000;
        function pack(index, previous) {
            if (index===wanted.length) return previous;
            var item=wanted[index], xs=[edge,Math.round(item.x/cell)*cell,Math.floor((area.width-edge-item.width)/cell)*cell];
            var ys=[edge,Math.round(item.y/cell)*cell,Math.floor((area.height-edge-item.height)/cell)*cell];
            previous.forEach(function(p) {
                xs.push(p.x+p.width+gap,p.x-item.width-gap);
                ys.push(p.y+p.height+gap,p.y-item.height-gap);
            });
            xs=xs.filter(function(x,i){return x>=edge && x+item.width<=area.width-edge && xs.indexOf(x)===i;});
            ys=ys.filter(function(y,i){return y>=edge && y+item.height<=area.height-edge && ys.indexOf(y)===i;});
            var candidates=[];
            xs.forEach(function(x){ys.forEach(function(y){
                var r={id:item.id,x:x,y:y,width:item.width,height:item.height};
                if (!previous.some(function(p){return overlaps(p,r,gap);})) candidates.push(r);
            });});
            candidates.sort(function(a,b){return Math.pow(a.x-item.x,2)+Math.pow(a.y-item.y,2)-Math.pow(b.x-item.x,2)-Math.pow(b.y-item.y,2);});
            for (var i=0;i<candidates.length && --budget>0;i++) {
                var result=pack(index+1,previous.concat([candidates[i]]));
                if(result) return result;
            }
            return null;
        }
        return pack(0,[]) || placed;
    }
    return placed;
}

function beside(anchor, size, screen, gap) {
    var edge = 8;
    var left = anchor.x-screen.x, right = screen.x+screen.width-anchor.x-anchor.width;
    // Both calendars open toward the screen's centre, independent of text direction.
    var x = left >= right ? anchor.x-size.width-gap : anchor.x+anchor.width+gap;
    return {x:Math.max(screen.x+edge,Math.min(x,screen.x+screen.width-size.width-edge)),
            y:Math.max(screen.y+edge,Math.min(anchor.y,screen.y+screen.height-size.height-edge))};
}
