import warnings

import cupy
import cupyx

from cupyx.scipy.ndimage import _util
from cupyx.scipy.ndimage import filters


def choose_conv_method(in1, in2, mode='full'):
    """Find the fastest convolution/correlation method.

    Args:
        in1 (cupy.ndarray): first input.
        in2 (cupy.ndarray): second input.
        mode (str, optional): ``valid``, ``same``, ``full``.

    Returns:
        str: A string indicating which convolution method is fastest,
        either ``direct`` or ``fft``.

    .. warning::
        This function currently doesn't support measure option,
        nor multidimensional inputs. It does not guarantee
        the compatibility of the return value to SciPy's one.

    .. seealso:: :func:`scipy.signal.choose_conv_method`

    """
    if in1.ndim != 1 or in2.ndim != 1:
        raise NotImplementedError('Only 1d inputs are supported currently')

    if in1.dtype.kind in 'bui' or in2.dtype.kind in 'bui':
        return 'direct'

    if _fftconv_faster(in1, in2, mode):
        return 'fft'

    return 'direct'


def _fftconv_faster(x, h, mode):
    """
    .. seealso:: :func: `scipy.signal.signaltools._fftconv_faster`

    """
    # TODO(Dahlia-Chehata): replace with GPU-based constants.
    return True


def wiener(im, mysize=None, noise=None):
    """Perform a Wiener filter on an N-dimensional array.

    Apply a Wiener filter to the N-dimensional array `im`.

    Args:
        im (cupy.ndarray): An N-dimensional array.
        mysize (int or cupy.ndarray, optional): A scalar or an N-length list
            giving the size of the Wiener filter window in each dimension.
            Elements of mysize should be odd. If mysize is a scalar, then this
            scalar is used as the size in each dimension.
        noise (float, optional): The noise-power to use. If None, then noise is
            estimated as the average of the local variance of the input.

    Returns:
        cupy.ndarray: Wiener filtered result with the same shape as `im`.

    .. seealso:: :func:`scipy.signal.wiener`
    """
    if mysize is None:
        mysize = 3
    mysize = _util._fix_sequence_arg(mysize, im.ndim, 'mysize', int)
    im = im.astype(float, copy=False)

    # Estimate the local mean
    local_mean = filters.uniform_filter(im, mysize, mode='constant')

    # Estimate the local variance
    local_var = filters.uniform_filter(im*im, mysize, mode='constant')
    local_var -= local_mean*local_mean

    # Estimate the noise power if needed.
    if noise is None:
        noise = local_var.mean()

    # Perform the filtering
    res = im - local_mean
    res *= (1 - noise / local_var)
    res += local_mean
    return cupy.where(local_var < noise, local_mean, res)


def order_filter(a, domain, rank):
    """Perform an order filter on an N-D array.

    Perform an order filter on the array in. The domain argument acts as a mask
    centered over each pixel. The non-zero elements of domain are used to
    select elements surrounding each input pixel which are placed in a list.
    The list is sorted, and the output for that pixel is the element
    corresponding to rank in the sorted list.

    Args:
        a (cupy.ndarray): The N-dimensional input array.
        domain (cupy.ndarray): A mask array with the same number of dimensions
            as `a`. Each dimension should have an odd number of elements.
        rank (int): A non-negative integer which selects the element from the
            sorted list (0 corresponds to the smallest element).

    Returns:
        cupy.ndarray: The results of the order filter in an array with the same
            shape as `a`.

    .. seealso:: :func:`cupyx.scipy.ndimage.rank_filter`
    .. seealso:: :func:`scipy.signal.order_filter`
    """
    if any(x % 2 != 1 for x in domain.shape):
        raise ValueError("Each dimension of domain argument "
                         " should have an odd number of elements.")
    return filters.rank_filter(a, rank, footprint=domain, mode='constant')


def medfilt(volume, kernel_size=None):
    """Perform a median filter on an N-dimensional array.

    Apply a median filter to the input array using a local window-size
    given by `kernel_size`. The array will automatically be zero-padded.

    Args:
        volume (cupy.ndarray): An N-dimensional input array.
        kernel_size (int or list of ints): Gives the size of the median filter
            window in each dimension. Elements of `kernel_size` should be odd.
            If `kernel_size` is a scalar, then this scalar is used as the size
            in each dimension. Default size is 3 for each dimension.

    Returns:
        cupy.ndarray: An array the same size as input containing the median
        filtered result.

    .. seealso:: :func:`cupyx.scipy.ndimage.median_filter`
    .. seealso:: :func:`scipy.signal.medfilt`
    """
    # output is forced to float64 to match scipy
    kernel_size = _get_kernel_size(kernel_size, volume.ndim)
    if any(k > s for k, s in zip(kernel_size, volume.shape)):
        warnings.warn('kernel_size exceeds volume extent: '
                      'volume will be zero-padded')

    size = cupy.core.internal.prod(kernel_size)
    return filters.rank_filter(volume, size // 2, size=kernel_size,
                               output=float, mode='constant')


def medfilt2d(input, kernel_size=3):
    """Median filter a 2-dimensional array.

    Apply a median filter to the `input` array using a local window-size given
    by `kernel_size` (must be odd). The array is zero-padded automatically.

    Args:
        input (cupy.ndarray): A 2-dimensional input array.
        kernel_size (int of list of ints of length 2): Gives the size of the
            median filter window in each dimension. Elements of `kernel_size`
            should be odd. If `kernel_size` is a scalar, then this scalar is
            used as the size in each dimension. Default is a kernel of size
            (3, 3).

    Returns:
        cupy.ndarray: An array the same size as input containing the median
            filtered result.
    See also
    --------
    .. seealso:: :func:`cupyx.scipy.ndimage.median_filter`
    .. seealso:: :func:`cupyx.scipy.signal.medfilt`
    .. seealso:: :func:`scipy.signal.medfilt2d`
    """
    # Scipy's version only supports uint8, float32, and float64
    if input.ndim != 2:
        raise ValueError('input must be 2d')
    kernel_size = _get_kernel_size(kernel_size, input.ndim)
    order = kernel_size[0] * kernel_size[1] // 2
    return filters.rank_filter(input, order, size=kernel_size, mode='constant')


def _get_kernel_size(kernel_size, ndim):
    if kernel_size is None:
        kernel_size = (3,) * ndim
    kernel_size = ._util._fix_sequence_arg(kernel_size, ndim,
                                           'kernel_size', int)
    if any((k % 2) != 1 for k in kernel_size):
        raise ValueError("Each element of kernel_size should be odd")
    return kernel_size
