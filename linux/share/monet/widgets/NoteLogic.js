function key(day) {
    return String(day.getFullYear()).padStart(4,"0")+"-"+String(day.getMonth()+1).padStart(2,"0")+"-"+String(day.getDate()).padStart(2,"0");
}
function repeating(value) {
    return ["daily","weekly","monthly","yearly"].indexOf(value)>=0;
}
function calendarDate(year, month, day) {
    var date=new Date(0);
    date.setHours(12,0,0,0);
    date.setFullYear(year,month,day);
    return date;
}
function parse(date) {
    var parts=date.split("-").map(Number);
    return calendarDate(parts[0],parts[1]-1,parts[2]);
}
// Calendar days, not elapsed local hours: a week can cross a daylight-saving change.
function dayNumber(day) {
    var utc=new Date(0);
    utc.setUTCFullYear(day.getFullYear(),day.getMonth(),day.getDate());
    return utc.getTime()/86400000;
}
function occurs(start, day, recurrence) {
    var date=key(day);
    if (start>date) return false;
    if (recurrence==="daily") return true;
    if (recurrence==="weekly") return (dayNumber(day)-dayNumber(parse(start)))%7===0;
    if (recurrence==="monthly") return start.slice(8)===date.slice(8);
    return recurrence==="yearly" && start.slice(5)===date.slice(5);
}
function source(notes, day) {
    var date=key(day);
    if (notes[date] !== undefined) return date;
    return Object.keys(notes).filter(k => notes[k] && occurs(k,day,notes[k].repeat)).sort().pop() || date;
}
function text(notes, day) {
    var note=notes[source(notes,day)];
    return typeof note==="string" ? note : note && note.text || "";
}
function repeat(notes, day) {
    var note=notes[source(notes,day)];
    return note && repeating(note.repeat) ? note.repeat : "none";
}
function updated(notes, day, value, recurrence) {
    var all=Object.assign({},notes), origin=source(notes,day);
    if (!value.trim()) delete all[origin];
    else if (repeating(recurrence)) {
        // Changing the interval starts it on the day being edited, so switching
        // a future weekly occurrence to monthly doesn't move it to another date.
        if (recurrence!==repeat(notes,day)) { delete all[origin]; origin=key(day); }
        all[origin]={text:value,repeat:recurrence};
    }
    else { delete all[origin]; all[key(day)]=value; }
    return all;
}
function nextOccurrence(start, day, recurrence) {
    var first=parse(start), from=key(day);
    if (start>from) return first;
    if (recurrence==="daily" || recurrence==="weekly") {
        var interval=recurrence==="daily" ? 1 : 7;
        var distance=dayNumber(day)-dayNumber(first);
        return calendarDate(day.getFullYear(),day.getMonth(),day.getDate()+interval-distance%interval);
    }
    if (recurrence==="monthly") {
        for (var offset=0; offset<13; offset++) {
            var month=calendarDate(day.getFullYear(),day.getMonth()+offset,1);
            var candidate=calendarDate(month.getFullYear(),month.getMonth(),first.getDate());
            if (candidate.getMonth()===month.getMonth() && key(candidate)>from) return candidate;
        }
    } else if (recurrence==="yearly") {
        // Eight years covers the leap-day gap around non-leap century years.
        for (var year=day.getFullYear(); year<=day.getFullYear()+8; year++) {
            var next=calendarDate(year,first.getMonth(),first.getDate());
            if (next.getMonth()===first.getMonth() && next.getDate()===first.getDate() && key(next)>from) return next;
        }
    }
    return null;
}
function after(notes, day, count) {
    var candidates={};
    Object.keys(notes).forEach(k => {
        var entry=notes[k], cursor=day;
        for (var i=0; i<(entry && repeating(entry.repeat) ? count : 1); i++) {
            var next=nextOccurrence(k,cursor,entry && entry.repeat);
            if (!next) break;
            candidates[key(next)]=next;
            cursor=next;
        }
    });
    return Object.keys(candidates).sort().slice(0,count).map(k => ({day:candidates[k],text:text(notes,candidates[k])}));
}
