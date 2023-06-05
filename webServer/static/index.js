$.ajax ({
    url: '/data',
    datatype: "json",
    success: function (elements) {
        console.log(elements['dati']);
        elements['dati'].forEach(element => $('#dati').append ("<tr><td>" + element['Station'] + "</td>" + "<td>" + element["Date"] + "</td>" + "<td>" + element["MaxT"] + "</td>" + "<td>" + element["MinT"] + "</td>" + "<td>" + element["RH1"] + "</td>" + "<td>" + element["RH2"] + "</td>" + "<td>" + element["Wind"] + "</td>" + "<td>" + element["Rain"] + "</td>" + "</tr>"));

    }
})




