class IntervalProcessor():
    '''
    The IntervalProcessor class provides methods to work
    with interval representations of melodies
    '''

    note_values = {
        "9": 0, "a": 1, "b": 2, "c": 3, "d": 4,
        "e": 5, "f": 6, "g": 7, "h": 8, "j": 9,
        "k": 10, "l": 11, "m": 12, "n": 13, "o": 14,
        "p": 15, "q": 16, "r": 17, "s": 18,

        ")": 0, "A": 1, "B": 2, "C": 3, "D": 4,
        "E": 5, "F": 6, "G": 7, "H": 8, "J": 9,
        "K": 10, "L": 11, "M": 12, "N": 13, "O": 14,
        "P": 15, "Q": 16, "R": 17, "S": 18
    }

    interval_markers = "abcdefghjklmnopqrstABCDEFGHJKLMNOPQRST"

    volpiano_notes = "9abcdefghjklmnopqrs)ABCDEFGHJKLMNOPQRS"


    @classmethod
    def transform_volpiano_to_intervals(cls, volpiano):
        '''
        Calculate the interval representation of a volpiano-encoded melody
        '''
        seen_first_note = False
        previous_note = None
        interval_repr = ""

        for c in volpiano:
            if c in cls.volpiano_notes:
                if seen_first_note:
                    (interval_value, lower_first) =\
                        cls._calculate_interval(previous_note, c)
                    marker = cls._interval_to_marker(interval_value, lower_first)

                    interval_repr += marker
                    previous_note = c
                else:
                    seen_first_note = True
                    cls._first_note = c
                    previous_note = c
                    interval_repr += c
            else:
                interval_repr += c

        return interval_repr


    @classmethod
    def transform_intervals_to_volpiano(cls, interval_repr):
        '''
        Calculate the volpiano-encoding of an interval-represented melody
        '''
        seen_first_note = False
        previous_note = None
        volpiano = ""

        for c in interval_repr:
            if c in cls.interval_markers and seen_first_note:
                interval_value = cls._get_interval_from_marker(c)
                note = cls._get_next_note_in_interval(previous_note, interval_value)
                previous_note = note
                volpiano += note
            elif c in cls.volpiano_notes and not seen_first_note:
                seen_first_note = True
                previous_note = c
                volpiano += c
            else:
                volpiano += c

        return volpiano


    @classmethod
    def _calculate_interval(cls, note_a, note_b):
        value_a = cls.note_values[note_a]
        value_b = cls.note_values[note_b]
        interval_value = abs(value_b - value_a)

        interval_is_negative = True if note_a > note_b else False

        return (interval_value, interval_is_negative)

        
    @classmethod
    def _interval_to_marker(cls, interval_value, interval_is_negative):

        marker = cls.interval_markers[interval_value]

        # if interval is negative, return uppercase char
        if interval_is_negative:
            marker = marker.upper()

        return marker


    @classmethod
    def _get_interval_from_marker(cls, interval_marker):
        interval_is_negative = interval_marker.isupper()
        
        interval_marker_lower = interval_marker.lower()
        interval_value = cls.interval_markers.index(interval_marker_lower)
        if interval_is_negative:
            interval_value *= -1

        return interval_value


    @classmethod
    def _get_next_note_in_interval(cls, start_note, interval):
        is_liquescent = start_note.isupper()
        start_note = start_note.lower()

        start_note_index = cls.volpiano_notes.index(start_note)
        next_note = cls.volpiano_notes[start_note_index + interval]
        if is_liquescent:
            next_note = next_note.upper()
        return next_note

