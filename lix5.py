# file size, sample length, min. mask length, chunk size
FS = 331
SL = 3
MML = 1
CS = 256
bb = b'X' * FS



def _parse_mini_header(bb):
    pass


def _parse_mask(b):
    return 1



def _parse_sample(bb):
    pass



def parse_file():
    i = 0
    need_parse_mini = 1

    while 1:
        if i + SL + MML > FS:
            # real or padded
            print(f'end at {i}, FS {FS}, remain {FS - i}')
            break

        if i % CS == 0:
            need_parse_mini = 1
            i += 8
            print(f'{i - 8} - {i} (8)')

        if need_parse_mini:
            m = (i // CS) * CS
            print(f'mini at {m}')
            _parse_mini_header(bb[m])

        n_mask = _parse_mask(bb[i])

        if (i % CS) + n_mask + SL > CS:
            n_pre = CS - (i % CS)
            n_post = SL + n_mask - n_pre
            j = i + n_pre + 8
            s = bb[i:i+n_pre] + bb[j:j+n_post]
            print(f'{i} - {i+n_pre} ({n_pre}) + {j}:{j+n_post} ({n_post})')
            j += n_post
            need_parse_mini = 1
        else:
            j = i + n_mask + SL
            s = bb[i:j]
            print(f'{i} - {j} ({j - i})')
            need_parse_mini = 0

        _parse_sample(s[n_mask:])
        i = j



if __name__ == '__main__':
    parse_file()
    
