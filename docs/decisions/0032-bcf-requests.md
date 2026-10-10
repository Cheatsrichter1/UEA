# 0032: Requests as BCF

Status: Accepted (export built)
Date: 2026-10-10

## Context

Requests are how one discipline asks another for something (`0010-requests-in-the-model.md`): `req q1 elec w7 "Schlitz 10x5 cm"`. Between agents in one project they work as they are. But an imported architecture belongs to an architect who works outside UEA (`0011-ifc-import.md`), in Archicad, Revit or Allplan, often with BIMcollab or Solibri beside it. The format those programs share for "look at this element, here is the question" is BCF (BIM Collaboration Format, buildingSMART): a zip of topics, each with a title, a status, comments and viewpoints that select elements by their IFC GlobalId and set a camera.

## Decision

**`uea export bcf [discipline]`** writes the requests whose targets belong to that discipline (default `arch`, the architect) to `out/<project>-<discipline>.bcf`, BCF 2.1, the version the programs above read today. The output names the file, the number of topics and the open requests: `out/haus-arch.bcf BCF 2.1: 2 topics, open: q1`. A discipline without requests is an error (`no requests to arch`).

**One topic per request**, open or not:
- Guid: derived from the project and the request id, so it is the same in every export, and a program that holds the topic updates it. Request ids are never reused (`0009`).
- Type `Request`; status `Open`, or `Closed` when done or rejected. The title is the request's text as written; the label is the asking discipline (`Elektroplanung`); author and date are those of the batch that added it (its `--by`).
- The description, in German like every export for humans: `Anfrage q1 der Elektroplanung an die Architektur. Betrifft: w7 (Wand). Aus UEA (haus, Stand 14).`
- A closed request gets a comment by who closed it: `Erledigt (Stand 15).` or `Abgelehnt: <reason>`, and the topic's modified date and author.

**The viewpoint** selects the targets and looks at them:
- Each target by its GlobalId in the architect's file where it was imported (from the import's history entry), else by the GlobalId UEA's own IFC export gives it (`uea/export/guid.py`, one function for both), so the topic works against either model.
- A perspective camera 6 m south-west of the targets' middle and 4 m above it, looking at it, in the coordinates of the architect's file: the import's move and turn (`0031`) and the height of ±0.00 are undone. A target UEA cannot place (a device, a type) is selected without moving the camera.
- No snapshot: the programs render their own.

**Not built: reading BCF back.** The architect answers in the next IFC (which a re-import brings in) and in the topic's comments. An agent then closes or rejects the request with a batch. A `uea import bcf` that lists the replies against the requests is the next step once a real round trip shows what the programs write into a topic.

## Alternatives

- **BCF 3.0.** Newer, with a REST API in mind, but not yet read by all the programs offices use; 2.1 is.
- **The bcf-client library.** Little to gain for writing three small XML files into a zip, and one more dependency; the standard library writes them.
- **Only open requests.** A program would keep showing a topic as open that UEA has closed.
- **One BCF per request, or topics for issues too.** Issues are for the discipline that owns them, inside UEA; a request is what is addressed to someone.

## Consequences

- Tested (`tests/test_bcf.py`): topics of open, done and rejected requests on a project made in UEA, with the GlobalIds of UEA's export; the GlobalIds of an imported file's elements and a camera that looks at the middle of the wall in the survey coordinates of a file 485 km east, 5520 km north and turned by 30° (within 2 mm). `compress` matches IfcOpenShell's GlobalIds.
- Not checked yet against a BCF schema validator or opened in Archicad, Revit or BIMcollab. The user does that with a real file.
- The export help names it (+31 tokens in `help export`; +3 in the reading of the help, `bcf` in the list of formats).
