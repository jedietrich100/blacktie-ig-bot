"""Gentle everyday humor, rotating without repeats for 60 days."""
import datetime as dt

START = dt.date(2026, 10, 1)
JOKES = [
    ("I added 'relax' to my to-do list.", "Now I'm behind on that too."),
    ("My laundry has entered its next phase.", "Chair."),
    ("I went into the kitchen for a reason.", "The refrigerator and I are investigating."),
    ("My phone says my screen time is down.", "Apparently naps count as self-improvement."),
    ("I bought a planner to get organized.", "It's somewhere very organized."),
    ("The recipe said 'a pinch of salt.'", "Finally, a measurement that respects my qualifications."),
    ("My plants and I have a lot in common.", "We both perk up when someone remembers the water."),
    ("I cleaned out my junk drawer.", "Now I have a junk counter."),
    ("I set five alarms this morning.", "It was less a wake-up call and more a negotiation."),
    ("I folded a fitted sheet.", "The result is legally a shape."),
    ("My calendar has a free afternoon.", "I penciled in being surprised."),
    ("I opened one browser tab to finish a task.", "The other 26 are emotional support."),
    ("I have a favorite grocery-store checkout lane.", "Adulthood really sneaks up on you."),
    ("I took the stairs today.", "They seemed as surprised as I was."),
    ("The leftovers said 'eat me.'", "The dishes said 'let's not rush into anything.'"),
    ("I put my keys in a safe place.", "Even I can't get to them."),
    ("My suitcase is packed for three days.", "And five imaginary emergencies."),
    ("I started a new morning routine.", "So far, the morning is winning."),
    ("The dishwasher is full.", "Time to play everyone's least favorite puzzle."),
    ("I went shopping with a list.", "The snacks made several helpful suggestions."),
    ("I cleared my inbox.", "For one beautiful second, I was a different person."),
    ("I asked my dog what we should do today.", "Apparently we're circling back to snacks."),
    ("I finally used the fancy notebook.", "First entry: buy more notebooks."),
    ("I love a quick errand.", "Especially the part where it becomes four errands."),
    ("My coffee went cold while I got ready.", "It also gave up on the schedule."),
    ("I organized the cables behind my desk.", "They're now tangled by category."),
    ("I sat down for five minutes.", "The couch has requested an extension."),
    ("My weather app says 'feels like.'", "Nice to see technology expressing itself."),
    ("I brought a reusable bag to the store.", "It enjoyed the trip from the back seat."),
    ("I made a meal plan.", "Then dinner arrived with its own opinions."),
    ("I found a parking spot on the first try.", "Trying to stay humble."),
    ("My socks disappear in the dryer.", "Honestly, I respect their sense of adventure."),
    ("I started cleaning one shelf.", "I now know what I was doing in 2014."),
    ("I learned a new keyboard shortcut.", "I'm accepting small technology awards."),
    ("I said I'd just browse the bookstore.", "The books heard 'come home with me.'"),
    ("My shopping cart had one squeaky wheel.", "We released a full album by aisle seven."),
    ("I checked the time on my phone.", "I can now tell you everything except the time."),
    ("I have a system for remembering passwords.", "It's called 'forgot password.'"),
    ("I cleaned my glasses.", "The world has apparently been in high definition all along."),
    ("My package arrived in a giant box.", "The tiny item seems pleased with its apartment."),
    ("I made a backup plan.", "It's also hoping the original plan works."),
    ("I watered the plants before breakfast.", "We're all trying to get our lives together."),
    ("I found the missing remote.", "It was under the thing I said it couldn't be under."),
    ("I chose the shortest line.", "It immediately developed a plot."),
    ("I put on shoes to feel productive.", "The couch accepted my business-casual approach."),
    ("My soup was too hot to eat.", "So naturally I kept checking every three seconds."),
    ("I deleted blurry photos from my phone.", "My thumb has never worked harder for clarity."),
    ("I planned to leave early.", "My keys, shoes, and water bottle scheduled separate meetings."),
    ("I bought a storage basket.", "My clutter now has better housing."),
    ("I read the assembly instructions first.", "I wanted the furniture to feel supported."),
    ("I took a shortcut on my walk.", "It came with a complimentary extra walk."),
    ("My favorite pen ran out of ink.", "The other pens know they're substitutes."),
    ("I put something in the oven and set a timer.", "For once, someone in this kitchen has a deadline."),
    ("I returned a shopping cart in one smooth motion.", "Waiting for the highlight reel."),
    ("I found an extra fry in the bag.", "The day has been promoted."),
    ("I tried to open a bag quietly.", "The bag had an announcement."),
    ("I remembered why I walked into the room.", "Unfortunately, I was already in a different room."),
    ("I finished a whole tube of lip balm.", "I'd like to thank every pocket involved."),
    ("I have a plan for the weekend.", "It starts with seeing how the first nap goes."),
    ("I finally paired every sock.", "Please respect my privacy during this historic moment."),
]


def for_day(day):
    index = (dt.date.fromisoformat(day) - START).days % len(JOKES)
    setup, punchline = JOKES[index]
    tagline = 'A very productive kind of unproductive. 🥜' if index == 0 else 'Your daily handful of funny. 🥜'
    caption = f'{setup}\n{punchline}\n\n{tagline}\n\n#CircusPeanutsDaily #DailyLaugh'
    return setup, punchline, caption
