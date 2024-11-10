import string

class IntervalProcessor():
    '''
    The IntervalProcessor class provides methods to work
    with interval representations of melodies
    ''' 
    halftone_encode = {key: (list(string.ascii_uppercase[::-1]) + list(string.ascii_lowercase))[i] 
                       for i, key in enumerate(range(-26, 26))}

    halftone_offsets = {
        "(": 0, "8": 0,  # f
        ")": 2, "9": 2,  # g
        "A": 4, "a": 4,  # a
        "Y": 5, "y": 5,  # bb
        "B": 6, "b": 6,  # b
        "C": 7, "c": 7,  # c'
        "D": 9, "d": 9,  # d'
        "E": 11, "e": 11,  # e'
        "F": 12, "f": 12, # f'
        "G": 14, "g": 14, # g'
        "H": 16, "h": 16, # a'
        "I": 17, "i": 17, # bb'
        "J": 18, "j": 18, # b'
        "K": 19, "k": 19, # c''
        "L": 21, "l": 21, # d''
        "X": 22, "x": 22, # eb''
        "M": 23, "m": 23, # e''
        "N": 24, "n": 24, # f''
        "O": 26, "o": 26, # g''
        "P": 28, "p": 28, # a''
        "Z": 29, "z": 29, # bb''
        "Q": 30, "q": 30, # b''
        "R": 31, "r": 31, # c'''
        "S": 33, "s": 33, # d'''
    }

    offset_tones = {
        0: "8",
        2: "9",
        4: "a",
        5: "y",
        6: "b",
        7: "c",
        9: "d",
        11: "e",
        12: "f",
        14: "g",
        16: "h",
        17: "i",
        18: "j",
        19: "k",
        21: "l",
        22: "x",
        23: "m",
        24: "n",
        26: "o",
        28: "p",
        29: "z",
        30: "q",
        31: "r",
        33: "s"
    }


    @classmethod
    def transform_volpiano_to_intervals(cls, volpiano):
        '''
        Calculate the interval representation of a volpiano-encoded melody
        '''
        seen_first_note = False
        previous_note = None
        interval_repr = ""
        for c in volpiano:
            if c in cls.halftone_offsets:
                if seen_first_note:
                    diff = cls.halftone_offsets[c] - cls.halftone_offsets[previous_note]
                    marker = cls.halftone_encode[diff]
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
        reversed_halftone_map = {value: key for key, value in cls.halftone_encode.items()}

        for c in interval_repr:
            if c in reversed_halftone_map and seen_first_note:
                interval_value = reversed_halftone_map[c]
                note = cls._get_next_note_in_interval(previous_note, interval_value)
                previous_note = note
                volpiano += note
            elif c in cls.halftone_offsets and not seen_first_note:
                seen_first_note = True
                previous_note = c
                volpiano += c
            else:
                volpiano += c

        return volpiano



    @classmethod
    def _get_next_note_in_interval(cls, start_note, interval):
        halftone_offset = cls.halftone_offsets[start_note] + interval
        return cls.offset_tones[halftone_offset]


